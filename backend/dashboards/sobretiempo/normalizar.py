"""
================================================================================
NORMALIZADOR DE SOBRETIEMPO -> SQLITE
================================================================================
Convierte el Excel en bruto "Control de Sobretiempo" (hojas DETALLE 2,0 y
PPTO 2026) y carga 4 tablas normalizadas a la base SQLite propia del
dashboard de Sobretiempo (Sobretiempo/data/sobretiempo.db):

    - sobretiempo_detalle           : transaccional, un registro por persona/concepto/mes
    - sobretiempo_presupuesto       : presupuesto del año despivoteado (mes en filas)
    - sobretiempo_resumen           : cruce Real vs Presupuesto por Ceco + Cuenta + Mes
    - sobretiempo_resumen_gerencia  : cruce Real vs Presupuesto por Gerencia + Subgerencia + Mes

Cada corrida REEMPLAZA por completo las 4 tablas (el Excel de origen ya trae
el acumulado completo del año a esa fecha, no hace falta mergear meses). Antes
de reemplazarlas se guarda un respaldo de la base anterior en
Sobretiempo/data/backups/, por si hay que volver atras mientras se resuelve
algun problema con el archivo nuevo.

Usado tanto por Sobretiempo/normalizar_sobretiempo.py (linea de comandos,
uso manual) como por el endpoint de carga del dashboard (subida desde la
pagina web) — la logica de parsing vive en un solo lugar.
"""

import shutil
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import Boolean, Date

from backend.dashboards.sobretiempo.db import (
    DB_DIR,
    DB_PATH,
    TABLE_DETALLE,
    TABLE_PRESUPUESTO,
    TABLE_RESUMEN,
    TABLE_RESUMEN_GERENCIA,
    engine,
)

SHEET_DETALLE = "DETALLE 2,0"
SHEET_PPTO = "PPTO 2026"

MESES_ORDEN = {
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
    "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10,
    "Noviembre": 11, "Diciembre": 12,
}
MESES_INV = {v: k for k, v in MESES_ORDEN.items()}
# Etiqueta de mes con número al inicio (ej. "01-Enero") para que las tablas
# ordenen bien como texto sin depender de un ordenamiento aparte.
MESES_LABEL = {v: f"{v:02d}-{k}" for k, v in MESES_ORDEN.items()}

# Códigos de Sociedad válidos (la hoja PPTO 2026 los usa en su tabla de
# detalle; sirven además para descartar de forma robusta la tabla-resumen
# que viene más abajo en la misma hoja, que reutiliza las mismas columnas
# con otro contenido)
SOCIEDAD_MAP = {
    "CC": "Chilquinta Energía S.A.",
    "CE": "Chilquinta Distribución S",
    "CS": "Chilquinta Servicios S.A.",
    "CX": "Chilquinta Transmisión S.",
    "CA": "Energ. de Casablanca S.A.",
    "LT": "C. Eléc. del Litoral S.A.",
    "LN": "Luzlinares S.A.",
    "LP": "Luzparral S.A.",
}


# ------------------------------------------------------------------------
# 1. LECTURA Y LIMPIEZA DE "DETALLE 2,0"
# ------------------------------------------------------------------------
def cargar_detalle(path):
    """
    La hoja trae filas basura arriba (filas 2-36, una matriz de referencia
    con Importe=0 que no es data real) y filas vacías al final. Solo son
    datos reales las filas donde 'Cód SAP' es numérico.
    """
    raw = pd.read_excel(path, sheet_name=SHEET_DETALLE, header=0)

    # Filtrar solo filas con Cód SAP numérico (descarta filas basura / vacías)
    raw = raw[pd.to_numeric(raw["Cód SAP"], errors="coerce").notna()].copy()

    # La hoja trae "Gerencia"/"Subgerencia"/"Unidad organizativa" DOS veces
    # (columnas duplicadas). Las segundas (posiciones 19-21) son la
    # jerarquía organizacional "oficial", la misma que usa PPTO 2026 para
    # cruzar por Ceco+Cuenta. Se usan esas.
    cols = list(raw.columns)
    gerencia_col = cols[19]
    subgerencia_col = cols[20]
    unidad_col = cols[21]

    df = pd.DataFrame({
        "Cod_SAP": raw["Cód SAP"].astype("Int64"),
        "Nombre_Personal": raw["Nombre de personal"],
        "RUT": raw["RUT"],
        "Sociedad": raw["Sociedad"],
        "Division_Personal": raw["División de personal"],
        "Gerencia": raw[gerencia_col],
        "Subgerencia": raw[subgerencia_col],
        "Unidad_Organizativa": raw[unidad_col],
        "Cargo": raw["Cargo"],
        "Area_Personal": raw["Área de Personal"],
        "Ceco": raw["Ceco"].fillna("").astype(str).str.strip(),
        "Cuenta_Contable": pd.to_numeric(raw["Cuenta contable"], errors="coerce").astype("Int64"),
        "OI": raw["OI"],
        "PEP": raw["PEP"],
        "Codigo_Concepto": raw["CC-n."],
        # "Concepto" es lo que se usa para agrupar/filtrar en el dashboard
        # (grafico "Gasto por concepto", filtro superior de Concepto) — se
        # tomo de "Clasif Haber" (columna W) a pedido del usuario, porque da
        # categorias limpias (Hora Extra, Turnos, Citacion, etc.) en vez de
        # las ~20 variantes granulares de "Texto expl.CC-nomina" (ej. "Horas
        # Extras 50%", "Rot. Turno Normal 50%"). Ese texto detallado no se
        # descarta, queda en Concepto_Detalle por si hace falta mas adelante
        # (no se usa en el dashboard todavia).
        "Concepto": raw["Clasif Haber"],
        "Concepto_Detalle": raw["Texto expl.CC-nómina"],
        "Clasif_Haber": raw["Clasif Haber"],
        "Clasificacion": raw["Clasificación"],
        "Cantidad_Horas": pd.to_numeric(raw["Cantid."], errors="coerce"),
        "Importe": pd.to_numeric(raw["   Importe"], errors="coerce"),
        "Validacion": raw["Validación"],
        "Anio": pd.to_numeric(raw[" Año"], errors="coerce").astype("Int64"),
        "Mes_Nombre": raw["Mes"],
    })

    df["Mes_Num"] = df["Mes_Nombre"].map(MESES_ORDEN).astype("Int64")
    df["Mes_Orden"] = df["Mes_Num"].map(MESES_LABEL)
    df["Fecha"] = df.apply(
        lambda r: date(int(r["Anio"]), int(r["Mes_Num"]), 1)
        if pd.notna(r["Anio"]) and pd.notna(r["Mes_Num"]) else None, axis=1
    )

    # Subcuenta = últimos 3 dígitos de la cuenta contable (mismo criterio que
    # la columna "Scta" de PPTO 2026)
    df["Subcuenta"] = df["Cuenta_Contable"].apply(
        lambda c: str(int(c))[-3:] if pd.notna(c) else None
    )

    # Ceco vacío = sobretiempo cargado directo a un PEP/proyecto en vez de
    # a un centro de costo (no tiene presupuesto CECO asociado)
    df["Ceco"] = df["Ceco"].replace("", "SIN CECO (Cargo a Proyecto)")

    return df


# ------------------------------------------------------------------------
# 2. ENRIQUECER DETALLE: flag de presupuesto asignado + mes cerrado
#    (mismos criterios que la hoja Resumen, para que ambas se lean de forma
#    consistente sin necesidad de recalcular nada en el frontend)
# ------------------------------------------------------------------------
def enriquecer_detalle(df_detalle, df_ppto):
    # Mismo criterio validado contra la presentación oficial: "con
    # presupuesto asignado" se define a nivel Ceco + Cuenta Contable.
    tiene_ppto = (
        df_ppto.groupby(["Ceco", "Cuenta_Contable"])["Presupuesto"].sum() > 0
    ).rename("Con_Presupuesto_Asignado").reset_index()
    df = df_detalle.merge(tiene_ppto, on=["Ceco", "Cuenta_Contable"], how="left")
    df["Con_Presupuesto_Asignado"] = df["Con_Presupuesto_Asignado"].fillna(False)

    ultimo_mes_cerrado = int(df.loc[df["Importe"] > 0, "Mes_Num"].max())
    df["Mes_Cerrado"] = df["Mes_Num"] <= ultimo_mes_cerrado
    return df


# ------------------------------------------------------------------------
# 2b. RESUMEN EJECUTIVO POR GERENCIA + SUBGERENCIA
#     (replica la tabla de seguimiento que usa Gerencia de Personas: ver
#     Control_Sobretiempo_presentación.pptx, diapositiva 3-4)
#
#     Metodología validada contra la presentación oficial:
#       - Solo se consideran cuentas CON presupuesto asignado (el gasto
#         cargado a PEP/proyecto, sin Ceco, queda fuera del avance
#         presupuestario -aunque sigue disponible en la tabla Detalle-)
#       - El "Presupuesto aprobado" es un monto FIJO ANUAL por Gerencia +
#         Subgerencia (no se compara contra un acumulado de presupuesto
#         mes a mes, sino contra el total aprobado para el año)
#       - "Trabajadores con HE" = cantidad de personas (Cód SAP) distintas
#         con sobretiempo, mensual y acumulado en el año
# ------------------------------------------------------------------------
KEY_GS = ["Gerencia", "Subgerencia"]


def construir_resumen_gerencia(df_detalle, df_ppto):
    # Nota metodológica importante: el filtro "con presupuesto asignado" se
    # evalúa a nivel Ceco + Cuenta Contable (columna Con_Presupuesto_Asignado
    # de Detalle). Se validó contra la presentación oficial que así es como
    # Gerencia de Personas define "cuentas presupuestadas": si el Ceco+Cuenta
    # tiene presupuesto en cualquier unidad, todo su gasto real cuenta
    # -aunque la unidad puntual que gastó no tenga su propia línea de
    # presupuesto-.
    det = df_detalle[df_detalle["Con_Presupuesto_Asignado"]].copy()

    anio = int(df_detalle["Anio"].dropna().iloc[0]) if df_detalle["Anio"].notna().any() else date.today().year
    ultimo_mes_cerrado = int(df_detalle.loc[df_detalle["Importe"] > 0, "Mes_Num"].max())

    ppto_anual = (
        df_ppto.groupby(KEY_GS)["Presupuesto"].sum()
        .rename("Presupuesto_Total_Anual").reset_index()
    )
    real_mes = (
        det.groupby(KEY_GS + ["Mes_Num"])["Importe"].sum()
        .rename("Importe_Real_Mes").reset_index()
    )
    head_mes = (
        det.groupby(KEY_GS + ["Mes_Num"])["Cod_SAP"].nunique()
        .rename("Trabajadores_Con_HE_Mes").reset_index()
    )

    # Universo: todas las combinaciones Gerencia+Subgerencia (de cualquiera
    # de las 2 fuentes) x los 12 meses del año
    combos = pd.concat([ppto_anual[KEY_GS], real_mes[KEY_GS]]).drop_duplicates()
    meses = pd.DataFrame({"Mes_Num": list(range(1, 13))})
    combos["_k"] = 1
    meses["_k"] = 1
    universo = combos.merge(meses, on="_k").drop(columns="_k")
    universo["Anio"] = anio

    r = (
        universo
        .merge(ppto_anual, on=KEY_GS, how="left")
        .merge(real_mes, on=KEY_GS + ["Mes_Num"], how="left")
        .merge(head_mes, on=KEY_GS + ["Mes_Num"], how="left")
    )
    r["Presupuesto_Total_Anual"] = r["Presupuesto_Total_Anual"].fillna(0)
    r["Importe_Real_Mes"] = r["Importe_Real_Mes"].fillna(0)
    r["Trabajadores_Con_HE_Mes"] = r["Trabajadores_Con_HE_Mes"].fillna(0).astype(int)

    r["Mes_Nombre"] = r["Mes_Num"].map(MESES_INV)
    r["Mes_Orden"] = r["Mes_Num"].map(MESES_LABEL)
    r["Fecha"] = r.apply(lambda x: date(int(x["Anio"]), int(x["Mes_Num"]), 1), axis=1)
    r["Mes_Cerrado"] = r["Mes_Num"] <= ultimo_mes_cerrado
    r = r.sort_values(KEY_GS + ["Mes_Num"]).reset_index(drop=True)

    # --- Acumulado de gasto real (YTD) ---
    r["Real_Acumulado"] = r.groupby(KEY_GS, sort=False)["Importe_Real_Mes"].cumsum()

    # --- Headcount acumulado (personas distintas con HE en lo que va del
    # año -> NO es la suma de los headcounts mensuales, porque la misma
    # persona puede repetirse mes a mes; se cuenta 1 vez desde su primer
    # mes con sobretiempo) ---
    primera_aparicion = (
        det.groupby(KEY_GS + ["Cod_SAP"])["Mes_Num"].min()
        .rename("Primer_Mes").reset_index()
    )
    altas_por_mes = (
        primera_aparicion.groupby(KEY_GS + ["Primer_Mes"]).size()
        .rename("Altas").reset_index()
        .rename(columns={"Primer_Mes": "Mes_Num"})
    )
    r = r.merge(altas_por_mes, on=KEY_GS + ["Mes_Num"], how="left")
    r["Altas"] = r["Altas"].fillna(0).astype(int)
    r["Trabajadores_Con_HE_Acumulado"] = r.groupby(KEY_GS, sort=False)["Altas"].cumsum()
    r = r.drop(columns="Altas")

    # --- Saldo, % ocupado y estado (contra el presupuesto ANUAL fijo) ---
    r["Saldo_Disponible"] = r["Presupuesto_Total_Anual"] - r["Real_Acumulado"]
    r["Pct_Ocupado"] = np.where(
        r["Presupuesto_Total_Anual"] > 0, r["Real_Acumulado"] / r["Presupuesto_Total_Anual"], np.nan
    )

    def estado(saldo, ppto, mes_cerrado):
        if ppto == 0:
            return "Sin Presupuesto"
        if not mes_cerrado:
            return "Mes Futuro (sin cierre)"
        return "Saldo a Favor" if saldo >= 0 else "Saldo en Contra"

    r["Estado"] = [estado(s, p, m) for s, p, m in
                   zip(r["Saldo_Disponible"], r["Presupuesto_Total_Anual"], r["Mes_Cerrado"])]

    cols_order = KEY_GS + [
        "Anio", "Mes_Num", "Mes_Nombre", "Mes_Orden", "Fecha", "Mes_Cerrado",
        "Presupuesto_Total_Anual", "Importe_Real_Mes", "Real_Acumulado", "Saldo_Disponible",
        "Pct_Ocupado", "Trabajadores_Con_HE_Mes", "Trabajadores_Con_HE_Acumulado", "Estado",
    ]
    return r[cols_order].sort_values(KEY_GS + ["Mes_Num"]).reset_index(drop=True)


# ------------------------------------------------------------------------
# 3. LECTURA Y DESPIVOTEO DE "PPTO 2026"
# ------------------------------------------------------------------------
def cargar_presupuesto(path):
    """
    La hoja PPTO 2026 trae el detalle real de presupuesto en la parte
    superior (formato ancho: un mes por columna). Más abajo en la MISMA
    hoja hay una segunda tabla-resumen (por Sociedad/Gerencia) que reutiliza
    los mismos nombres de columna con otro contenido. Para descartarla de
    forma robusta (sin depender de un número de fila fijo que puede
    correrse mes a mes) nos quedamos solo con filas cuya 'Sociedad' sea uno
    de los códigos válidos de 2 letras (CA/CC/CE/CS/CX/LN/LP/LT): ese
    patrón solo aparece en la tabla de detalle real.
    """
    raw = pd.read_excel(path, sheet_name=SHEET_PPTO, header=0)
    raw = raw[raw["Sociedad"].isin(SOCIEDAD_MAP.keys())].copy()

    meses_cols = [f"Suma de {m}" for m in MESES_ORDEN]
    meses_cols = [c for c in meses_cols if c in raw.columns]

    id_cols = {
        "Centro de Costo": "Ceco",
        "Cuenta": "Cuenta_Contable",
        "Scta": "Subcuenta",
        "Sociedad": "Sociedad",
        "Gerencia": "Gerencia",
        "Subgerencia": "Subgerencia",
        "Unidad organizativa": "Unidad_Organizativa",
    }
    base = raw[list(id_cols.keys()) + meses_cols].rename(columns=id_cols)
    base["Ceco"] = base["Ceco"].astype(str).str.strip()
    base["Cuenta_Contable"] = pd.to_numeric(base["Cuenta_Contable"], errors="coerce").round().astype("Int64")
    base["Subcuenta"] = pd.to_numeric(base["Subcuenta"], errors="coerce").round().astype("Int64").astype(str).str.zfill(3)
    # Estandarizar Sociedad: mismo nombre completo que usa la tabla Detalle
    base["Sociedad"] = base["Sociedad"].map(SOCIEDAD_MAP)

    # Despivotear: de "un mes por columna" a "una fila por mes"
    long_df = base.melt(
        id_vars=[c for c in id_cols.values()],
        value_vars=meses_cols,
        var_name="Mes_Nombre",
        value_name="Presupuesto",
    )
    long_df["Mes_Nombre"] = long_df["Mes_Nombre"].str.replace("Suma de ", "", regex=False)
    long_df["Mes_Num"] = long_df["Mes_Nombre"].map(MESES_ORDEN).astype("Int64")
    long_df["Mes_Orden"] = long_df["Mes_Num"].map(MESES_LABEL)
    long_df["Presupuesto"] = pd.to_numeric(long_df["Presupuesto"], errors="coerce").fillna(0)
    long_df["Anio"] = int(date.today().year)

    long_df["Fecha"] = long_df.apply(
        lambda r: date(int(r["Anio"]), int(r["Mes_Num"]), 1) if pd.notna(r["Mes_Num"]) else None,
        axis=1,
    )

    cols_order = ["Ceco", "Cuenta_Contable", "Subcuenta", "Sociedad", "Gerencia",
                  "Subgerencia", "Unidad_Organizativa", "Anio", "Mes_Num",
                  "Mes_Nombre", "Mes_Orden", "Fecha", "Presupuesto"]
    return long_df[cols_order].sort_values(["Ceco", "Cuenta_Contable", "Mes_Num"]).reset_index(drop=True)


# ------------------------------------------------------------------------
# 4. RESUMEN: CRUCE REAL VS PRESUPUESTO
#    Llave: Sociedad + Ceco + Cuenta + Gerencia + Subgerencia + Unidad + Mes
#    (Ceco+Cuenta es la llave pedida para cruzar; se agrega Gerencia /
#    Subgerencia / Unidad porque en los datos un mismo Ceco reparte
#    presupuesto entre varias Gerencias -> sin este detalle no se puede
#    saber qué área es "responsable" de cada línea de presupuesto)
#
#    Trae TODO precalculado: monto del mes, acumulado del año (YTD), saldo
#    mensual y acumulado, % de ejecución mensual y acumulado, estado y
#    flag de mes cerrado.
# ------------------------------------------------------------------------
KEY_ORG = ["Sociedad", "Ceco", "Cuenta_Contable", "Subcuenta",
           "Gerencia", "Subgerencia", "Unidad_Organizativa"]


def construir_resumen(df_detalle, df_ppto):
    real_agg = (
        df_detalle.groupby(KEY_ORG + ["Anio", "Mes_Num"], dropna=False)
        .agg(Importe_Real=("Importe", "sum"), Horas_Real=("Cantidad_Horas", "sum"))
        .reset_index()
    )
    ppto_agg = (
        df_ppto.groupby(KEY_ORG + ["Anio", "Mes_Num"], dropna=False)
        .agg(Presupuesto=("Presupuesto", "sum"))
        .reset_index()
    )

    # Universo completo: todas las combinaciones que existen en cualquiera
    # de las dos fuentes x los 12 meses del año -> permite ver meses
    # futuros ya presupuestados aunque aún no haya gasto real, y gasto
    # real sin presupuesto asignado ("Sin Presupuesto")
    combos = pd.concat([real_agg[KEY_ORG], ppto_agg[KEY_ORG]]).drop_duplicates()

    anio = int(df_detalle["Anio"].dropna().iloc[0]) if df_detalle["Anio"].notna().any() else date.today().year
    meses = pd.DataFrame({"Mes_Num": list(range(1, 13))})
    combos["_k"] = 1
    meses["_k"] = 1
    universo = combos.merge(meses, on="_k").drop(columns="_k")
    universo["Anio"] = anio

    resumen = (
        universo
        .merge(real_agg, on=KEY_ORG + ["Anio", "Mes_Num"], how="left")
        .merge(ppto_agg, on=KEY_ORG + ["Anio", "Mes_Num"], how="left")
    )
    resumen["Importe_Real"] = resumen["Importe_Real"].fillna(0)
    resumen["Horas_Real"] = resumen["Horas_Real"].fillna(0)
    resumen["Presupuesto"] = resumen["Presupuesto"].fillna(0)  # Sin Presupuesto -> 0

    # "Con presupuesto asignado" se evalúa a nivel Ceco + Cuenta Contable
    # (MISMO criterio que enriquecer_detalle()/construir_resumen_gerencia(),
    # validado contra la presentación oficial — ver comentario en
    # enriquecer_detalle). Ojo: NO se puede agrupar por KEY_ORG completo
    # (incluyendo Gerencia/Subgerencia/Unidad) — un mismo Ceco+Cuenta puede
    # tener presupuesto cargado bajo una Subgerencia y gasto real bajo otra
    # (ej. una diferencia de mayúsculas entre la hoja PPTO y la hoja
    # DETALLE, "Co Subgerencia..." vs "CO Subgerencia..."), y agrupar por
    # KEY_ORG completo dejaba ese gasto afuera del "% Gastado" (bug
    # encontrado 17-ago-2026 comparando el dashboard HTML contra el
    # informe PDF: el HTML mostraba $3.600.948 gastado en Gerencia de
    # Personas y el PDF/resumen_gerencia mostraba $9.930.397 — la cifra
    # correcta es la del PDF, el HTML estaba excluyendo por error ~$6.3M
    # de gasto real que sí tenía presupuesto asignado a su Ceco+Cuenta).
    tiene_ppto = df_ppto.groupby(["Ceco", "Cuenta_Contable"])["Presupuesto"].sum()
    tiene_ppto = (tiene_ppto > 0).rename("Con_Presupuesto_Asignado").reset_index()
    resumen = resumen.merge(tiene_ppto, on=["Ceco", "Cuenta_Contable"], how="left")
    resumen["Con_Presupuesto_Asignado"] = resumen["Con_Presupuesto_Asignado"].fillna(False)

    resumen["Mes_Nombre"] = resumen["Mes_Num"].map(MESES_INV)
    resumen["Mes_Orden"] = resumen["Mes_Num"].map(MESES_LABEL)
    resumen["Fecha"] = resumen.apply(lambda r: date(int(r["Anio"]), int(r["Mes_Num"]), 1), axis=1)

    # Ordenar por grupo + mes ANTES de calcular acumulados
    resumen = resumen.sort_values(KEY_ORG + ["Mes_Num"]).reset_index(drop=True)

    # --- Acumulados YTD (precalculados) ---
    grp = resumen.groupby(KEY_ORG, sort=False)
    resumen["Presupuesto_Acumulado"] = grp["Presupuesto"].cumsum()
    resumen["Real_Acumulado"] = grp["Importe_Real"].cumsum()
    resumen["Horas_Real_Acumulado"] = grp["Horas_Real"].cumsum()

    # --- Saldo (a favor si es positivo, en contra si es negativo) ---
    resumen["Saldo_Mes"] = resumen["Presupuesto"] - resumen["Importe_Real"]
    resumen["Saldo_Acumulado"] = resumen["Presupuesto_Acumulado"] - resumen["Real_Acumulado"]

    # --- % de ejecución mensual y acumulado ---
    resumen["Pct_Ejecucion_Mes"] = np.where(
        resumen["Presupuesto"] > 0, resumen["Importe_Real"] / resumen["Presupuesto"], np.nan
    )
    resumen["Pct_Ejecucion_Acumulado"] = np.where(
        resumen["Presupuesto_Acumulado"] > 0,
        resumen["Real_Acumulado"] / resumen["Presupuesto_Acumulado"], np.nan
    )

    # --- Último mes con datos reales cargados (para distinguir "aún no
    # llega la data de ese mes" de "gastó $0 ese mes") ---
    ultimo_mes_cerrado = int(df_detalle.loc[df_detalle["Importe"] > 0, "Mes_Num"].max())
    resumen["Mes_Cerrado"] = resumen["Mes_Num"] <= ultimo_mes_cerrado

    def estado(saldo, con_ppto, ppto_mes, mes_cerrado):
        if not con_ppto:
            return "Sin Presupuesto"
        if not mes_cerrado:
            return "Mes Futuro (sin cierre)"
        if ppto_mes == 0:
            return "Sin Presupuesto (mes)"
        return "Saldo a Favor" if saldo >= 0 else "Saldo en Contra"

    resumen["Estado_Mes"] = [
        estado(s, c, p, m) for s, c, p, m in zip(
            resumen["Saldo_Mes"], resumen["Con_Presupuesto_Asignado"],
            resumen["Presupuesto"], resumen["Mes_Cerrado"])
    ]
    resumen["Estado_Acumulado"] = [
        estado(s, c, p, m) for s, c, p, m in zip(
            resumen["Saldo_Acumulado"], resumen["Con_Presupuesto_Asignado"],
            resumen["Presupuesto_Acumulado"], resumen["Mes_Cerrado"])
    ]

    cols_order = KEY_ORG + [
        "Anio", "Mes_Num", "Mes_Nombre", "Mes_Orden", "Fecha", "Mes_Cerrado",
        "Importe_Real", "Horas_Real", "Presupuesto", "Saldo_Mes", "Pct_Ejecucion_Mes", "Estado_Mes",
        "Real_Acumulado", "Horas_Real_Acumulado", "Presupuesto_Acumulado", "Saldo_Acumulado",
        "Pct_Ejecucion_Acumulado", "Estado_Acumulado", "Con_Presupuesto_Asignado",
    ]
    return resumen[cols_order].sort_values(KEY_ORG + ["Mes_Num"]).reset_index(drop=True)


# ------------------------------------------------------------------------
# 5. RESPALDO + CARGA A SQLITE (reemplaza por completo las 4 tablas)
# ------------------------------------------------------------------------
BACKUPS_DIR = DB_DIR / "backups"


def respaldar_db() -> Path | None:
    """Copia la base actual a Sobretiempo/data/backups/ antes de sobrescribirla.

    Si todavia no existe ninguna base (primera carga), no hay nada que
    respaldar. El nombre incluye fecha y hora para no pisar respaldos
    anteriores.
    """
    if not DB_PATH.exists():
        return None
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = BACKUPS_DIR / f"sobretiempo_{timestamp}.db"
    shutil.copy2(DB_PATH, destino)
    return destino


def guardar_sqlite(df_detalle, df_ppto, df_resumen, df_resumen_ger):
    with engine.begin() as conn:
        df_detalle.to_sql(
            TABLE_DETALLE, conn, if_exists="replace", index=False,
            dtype={"Fecha": Date(), "Con_Presupuesto_Asignado": Boolean(), "Mes_Cerrado": Boolean()},
        )
        df_ppto.to_sql(
            TABLE_PRESUPUESTO, conn, if_exists="replace", index=False,
            dtype={"Fecha": Date()},
        )
        df_resumen.to_sql(
            TABLE_RESUMEN, conn, if_exists="replace", index=False,
            dtype={"Fecha": Date(), "Mes_Cerrado": Boolean(), "Con_Presupuesto_Asignado": Boolean()},
        )
        df_resumen_ger.to_sql(
            TABLE_RESUMEN_GERENCIA, conn, if_exists="replace", index=False,
            dtype={"Fecha": Date(), "Mes_Cerrado": Boolean()},
        )


def procesar_archivo(input_path) -> dict:
    """Corre todo el pipeline sobre un Excel y deja la base actualizada.

    Devuelve un resumen (cantidad de filas por tabla + ruta del respaldo,
    si se hizo uno) para mostrarle al usuario que subio el archivo. Si el
    Excel viene con un formato inesperado, cualquiera de los pasos de
    parsing de mas arriba tira una excepcion ANTES de tocar la base — el
    respaldo/reemplazo recien pasa al final, asi que un archivo invalido
    nunca deja la base a medio pisar.
    """
    df_detalle = cargar_detalle(input_path)
    df_ppto = cargar_presupuesto(input_path)
    df_detalle = enriquecer_detalle(df_detalle, df_ppto)
    df_resumen = construir_resumen(df_detalle, df_ppto)
    df_resumen_ger = construir_resumen_gerencia(df_detalle, df_ppto)

    backup = respaldar_db()
    guardar_sqlite(df_detalle, df_ppto, df_resumen, df_resumen_ger)

    return {
        "detalle": len(df_detalle),
        "presupuesto": len(df_ppto),
        "resumen": len(df_resumen),
        "resumen_gerencia": len(df_resumen_ger),
        "backup": str(backup) if backup else None,
    }
