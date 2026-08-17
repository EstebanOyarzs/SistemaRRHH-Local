"""
================================================================================
INFORMES EJECUTIVOS PDF DE SOBRETIEMPO, POR GERENCIA (sin servidor)
================================================================================
Genera un PDF por Gerencia con los indicadores de gasto/presupuesto de ESA
Gerencia únicamente (para mandárselo a cada gerente sin que vea las demás
áreas), a diferencia del reporte HTML de sobretiempo/reporte_html.py, que
es el dashboard completo con todas las Gerencias y filtros interactivos.

No requiere el backend corriendo, lee directo la base SQLite del dashboard,
igual que reporte_html.py. Usa reportlab (ya en requirements.txt) para armar
el PDF, sin depender de frontend/dist.

Metodología (misma que ya validó el usuario en el dashboard, ver CLAUDE.md
"Frontend" / sección Alerta y Resumen de SobretiempoDashboardPage.tsx):
    - **Opex vs. Capex** (agregado 17-ago-2026, a pedido del usuario): un
      Ceco es Opex si termina en "10099", Capex si no (incluye "SIN CECO
      (Cargo a Proyecto)"). TODO el informe (KPIs, Estado, Evolución
      mensual, Subgerencias, Concepto, Ranking principal) queda acotado a
      Opex — Capex solo aparece al final, como ranking complementario
      ("Ranking Capex"). Por eso la fuente de datos para KPIs/Estado/
      Subgerencias/Evolución pasó a ser sobretiempo_resumen (que sí tiene
      columna Ceco) en vez de sobretiempo_resumen_gerencia (agregada a
      nivel Gerencia+Subgerencia+Mes, sin Ceco — no se puede partir en
      Opex/Capex).
    - "Gastado/Disponible/Presupuesto anual" y "% Ejecutado" (KPIs + tabla
      de Subgerencias) = Real_Acumulado / Presupuesto_Total_Anual de
      sobretiempo_resumen (Con_Presupuesto_Asignado=1, solo Ceco Opex) al
      ULTIMO MES CERRADO, sumado sobre Subgerencias para el total de
      Gerencia. Mismo cálculo que el panel "Resumen" del dashboard, pero
      acotado a Opex (el dashboard no hace esta distinción).
    - "% Gastado" del semáforo de Estado = Pct_Ejecucion_Acumulado
      (Real_Acumulado / Presupuesto_Acumulado A LA FECHA, solo cuentas Opex
      con presupuesto asignado) agregado desde sobretiempo_resumen, mismo
      criterio y mismos umbrales (50%/70%) que la tabla "Alerta" del
      dashboard (que sí incluye Capex).
    - "Ritmo de gasto" = (Real_Acumulado / Presupuesto_Total_Anual) /
      (mes_referencia / 12), mismo cálculo que "Ritmo de gasto" del
      dashboard. A diferencia del dashboard (que en la tabla Alerta
      muestra el número "1.23x"), acá se muestra SOLO la palabra de estado
      resultante ("dentro de lo esperado"/"sobre lo esperado"/"excesivo a
      lo esperado"), sin el número ni el umbral, a pedido del usuario: el
      número es ruido para un gerente que solo necesita saber si va bien o
      mal.
    - "Gasto por Concepto" = sobretiempo_detalle filtrado a Ceco Opex (sin
      filtro de presupuesto asignado), igual que el panel "¿En que se
      gastó?" del dashboard pero acotado a Opex.
    - "Ranking de Colaboradores con mayores gastos" = Top 10 personas
      (Cod_SAP) con mayor Total acumulado en el año dentro de la Gerencia,
      agregado desde sobretiempo_detalle filtrado a Ceco Opex. Una fila por
      persona (no por transacción), con una columna de Importe por cada
      Concepto (Hora Extra, Turnos, Citación, etc.) + columna Total —
      mismo diseño pivoteado que el "Ranking de Importe" del dashboard
      HTML, agregado 17-ago-2026 para que una persona no aparezca repetida
      en filas separadas por transacción/mes/concepto (ver
      `_ranking_por_concepto()`).
    - "Ranking Capex" (agregado 17-ago-2026): mismo diseño pero calculado
      SOLO sobre Ceco Capex — información complementaria al final del
      informe, fuera del alcance Opex del resto del documento.
"""

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as _esc

import pandas as pd
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.config import PROJECT_ROOT
from backend.dashboards.sobretiempo.db import (
    TABLE_DETALLE,
    TABLE_RESUMEN,
    TABLE_RESUMEN_GERENCIA,
    engine,
)
from backend.dashboards.sobretiempo.normalizar import MESES_INV

REPORTES_DIR = PROJECT_ROOT / "Sobretiempo" / "data" / "reportes" / "gerencias"
TOP_N_PERSONAS = 10
ANCHO_CONTENIDO = 18 * cm  # A4 (21cm) - 1.5cm de margen a cada lado

# Logo corporativo del encabezado — compartido entre dashboards (no vive
# dentro de Sobretiempo/ porque no es especifico de este reporte).
LOGO_PATH = PROJECT_ROOT / "assets" / "logo_chilquinta.jpg"
LOGO_ANCHO = 5.2 * cm


def _logo_flowable(ancho: float = LOGO_ANCHO) -> Image | None:
    """Devuelve el logo como flowable, escalado a `ancho` manteniendo su
    proporcion real (leida del archivo, no hardcodeada). None si el archivo
    no existe — el informe se sigue generando igual, solo sin logo."""
    if not LOGO_PATH.exists():
        return None
    lector = ImageReader(str(LOGO_PATH))
    ancho_px, alto_px = lector.getSize()
    alto = ancho * alto_px / ancho_px
    return Image(str(LOGO_PATH), width=ancho, height=alto)

# Misma paleta que frontend/src/charts/registerCharts.ts (CHART_COLORS), para
# que el PDF se sienta consistente con el dashboard.
ROJO = colors.HexColor("#da291c")
NAVY = colors.HexColor("#2d3548")
SUCCESS = colors.HexColor("#0aa06e")
WARNING = colors.HexColor("#e0a800")
GRIS = colors.HexColor("#dee2e6")
GRIS_CLARO = colors.HexColor("#f3f3f3")
BLANCO = colors.white

# Mismos umbrales que SobretiempoDashboardPage.tsx (nivelAlerta/nivelRitmo)
UMBRAL_ADVERTENCIA = 0.5
UMBRAL_CRITICO = 0.7
RITMO_ADVERTENCIA = 1.0
RITMO_CRITICO = 1.3

NIVEL_COLOR = {"ok": SUCCESS, "advertencia": WARNING, "critico": ROJO}
NIVEL_LABEL = {
    "ok": "Dentro de lo esperado",
    "advertencia": "Atención",
    "critico": "Crítico",
}
# Palabra de estado para "Ritmo de gasto", a pedido del usuario, sin mostrar
# el número/umbral que arma el número, solo la conclusión en palabras.
PROGRESO_LABEL = {
    "ok": "Progreso de gasto dentro de lo esperado",
    "advertencia": "Progreso de gasto sobre lo esperado",
    "critico": "Progreso de gasto excesivo a lo esperado",
}

# Opex/Capex: a pedido del usuario (17-ago-2026), un Ceco es Opex si
# termina en "10099", Capex si no (incluye "SIN CECO (Cargo a Proyecto)").
# TODO el informe (KPIs, Estado, Evolucion mensual, Subgerencias, Concepto,
# Ranking principal) queda acotado a Opex — Capex solo aparece al final,
# como ranking complementario ("Ranking Capex").
OPEX_SUFIJO = "10099"


def _es_opex(ceco) -> bool:
    return isinstance(ceco, str) and ceco.endswith(OPEX_SUFIJO)


# Mismos 5 Concepto que el ranking pivoteado del dashboard HTML
# (CONCEPTOS_RANKING en SobretiempoDashboardPage.tsx) — se replican acá en
# vez de compartirse porque son proyectos separados (Python/TS) sin un
# canal de constantes compartidas.
CONCEPTOS_RANKING = [
    "Hora Extra",
    "Turnos",
    "Citación",
    "Rot Horas Extra/Turnos",
    "Bono Disponibilidad/Interluz/Alerta",
]
LABEL_CONCEPTO_CORTO = {
    "Rot Horas Extra/Turnos": "Rot HE/Turnos",
    "Bono Disponibilidad/Interluz/Alerta": "Bono Disp.",
}


def _ranking_por_concepto(df_fuente: pd.DataFrame) -> pd.DataFrame:
    """Ranking de personas con una fila por persona (Cod_SAP) y una columna
    de Importe por cada Concepto + Total — mismo diseño que el ranking del
    dashboard HTML, para no repetir a la misma persona en filas separadas
    por transaccion/mes/concepto (ver CLAUDE.md, bug de "Ranking de
    Importe" del 17-ago-2026). Top TOP_N_PERSONAS por Total."""
    columnas_vacias = ["Cod_SAP", "Nombre_Personal", "Total", "Horas"] + CONCEPTOS_RANKING
    if df_fuente.empty:
        return pd.DataFrame(columns=columnas_vacias)

    totales = (
        df_fuente.groupby(["Cod_SAP", "Nombre_Personal"], as_index=False)
        .agg(Total=("Importe", "sum"), Horas=("Cantidad_Horas", "sum"))
    )
    por_concepto = (
        df_fuente.groupby(["Cod_SAP", "Nombre_Personal", "Concepto"], as_index=False)["Importe"].sum()
        .pivot(index=["Cod_SAP", "Nombre_Personal"], columns="Concepto", values="Importe")
        .fillna(0.0)
        .reset_index()
    )
    for concepto in CONCEPTOS_RANKING:
        if concepto not in por_concepto.columns:
            por_concepto[concepto] = 0.0

    ranking = totales.merge(por_concepto, on=["Cod_SAP", "Nombre_Personal"], how="left")
    return ranking.sort_values("Total", ascending=False).head(TOP_N_PERSONAS).reset_index(drop=True)


def _fmt_clp(valor) -> str:
    if valor is None or pd.isna(valor):
        return "-"
    return "$" + f"{valor:,.0f}".replace(",", ".")


def _fmt_pct(valor) -> str:
    if valor is None or pd.isna(valor):
        return "-"
    return f"{valor * 100:.1f}%"


def _nivel_pct(pct_gastado: float | None) -> str:
    pct = pct_gastado or 0
    if pct >= UMBRAL_CRITICO:
        return "critico"
    if pct >= UMBRAL_ADVERTENCIA:
        return "advertencia"
    return "ok"


def _nivel_ritmo(ritmo: float | None) -> str:
    r = ritmo or 0
    if r >= RITMO_CRITICO:
        return "critico"
    if r >= RITMO_ADVERTENCIA:
        return "advertencia"
    return "ok"


def _nivel(pct_gastado: float | None, ritmo: float | None) -> str:
    """Nivel combinado (el peor de los dos indicadores), define el color
    general del semáforo de Estado."""
    niveles = (_nivel_pct(pct_gastado), _nivel_ritmo(ritmo))
    if "critico" in niveles:
        return "critico"
    if "advertencia" in niveles:
        return "advertencia"
    return "ok"


def _celda(texto, *, alineacion=TA_LEFT, negrita=False, tamano=8, color=None) -> Paragraph:
    """Paragraph para uso dentro de celdas de Table. A diferencia de un
    string plano, envuelve el texto en varias líneas si no entra en el
    ancho de columna (un string plano se sale de la celda y se superpone
    con la columna de al lado en vez de cortar línea)."""
    estilo = ParagraphStyle(
        "celda",
        fontName="Helvetica-Bold" if negrita else "Helvetica",
        fontSize=tamano,
        leading=tamano + 2.5,
        textColor=color or NAVY,
        alignment=alineacion,
    )
    valor = "-" if texto is None or (isinstance(texto, float) and pd.isna(texto)) else str(texto)
    return Paragraph(_esc(valor), estilo)


def _listar_gerencias() -> list[str]:
    df = pd.read_sql_query(
        f"SELECT DISTINCT Gerencia FROM {TABLE_RESUMEN_GERENCIA} "
        f"WHERE Gerencia IS NOT NULL AND TRIM(Gerencia) != '' ORDER BY Gerencia",
        engine,
    )
    return df["Gerencia"].tolist()


def _datos_gerencia(gerencia: str) -> dict | None:
    # sobretiempo_resumen (Ceco+Cuenta+Mes) es la unica fuente con columna
    # Ceco, asi que es la base de TODO lo de este informe (ya no
    # sobretiempo_resumen_gerencia, que esta pre-agregada a nivel Gerencia+
    # Subgerencia+Mes sin Ceco y por lo tanto no se puede partir en Opex/Capex).
    res = pd.read_sql_query(
        f"SELECT * FROM {TABLE_RESUMEN} WHERE Gerencia = :g",
        engine, params={"g": gerencia},
    )
    if res.empty or not (res["Mes_Cerrado"] == 1).any():
        return None

    anio = int(res["Anio"].iloc[0])
    ultimo_mes = int(res.loc[res["Mes_Cerrado"] == 1, "Mes_Num"].max())

    # Alcance del informe: SOLO Opex (Ceco terminado en "10099"). Capex
    # queda afuera de KPIs/Estado/Evolucion/Subgerencias/Concepto — solo
    # aparece al final como ranking complementario (Ranking Capex).
    res_opex = res[res["Ceco"].map(_es_opex)]
    res_opex_ppto = res_opex[res_opex["Con_Presupuesto_Asignado"] == 1]
    fila_mes = res_opex_ppto[res_opex_ppto["Mes_Num"] == ultimo_mes]

    presupuesto_anual = float(res_opex_ppto["Presupuesto"].sum())
    real_acumulado = float(fila_mes["Real_Acumulado"].sum())
    saldo_disponible = presupuesto_anual - real_acumulado
    pct_ocupado = real_acumulado / presupuesto_anual if presupuesto_anual > 0 else None
    ritmo = (pct_ocupado / (ultimo_mes / 12)) if pct_ocupado is not None else None

    # % Gastado "tipo Alerta", ver docstring del módulo (mismo alcance Opex).
    ppto_acum_res = float(fila_mes["Presupuesto_Acumulado"].sum())
    pct_gastado = real_acumulado / ppto_acum_res if ppto_acum_res > 0 else None

    ppto_por_sub = (
        res_opex_ppto.groupby("Subgerencia", as_index=False)["Presupuesto"].sum()
        .rename(columns={"Presupuesto": "Presupuesto_Total_Anual"})
    )
    real_por_sub = fila_mes.groupby("Subgerencia", as_index=False)["Real_Acumulado"].sum()
    subgerencias = ppto_por_sub.merge(real_por_sub, on="Subgerencia", how="left")
    subgerencias["Real_Acumulado"] = subgerencias["Real_Acumulado"].fillna(0.0)
    subgerencias["Saldo_Disponible"] = subgerencias["Presupuesto_Total_Anual"] - subgerencias["Real_Acumulado"]
    subgerencias["Pct_Ocupado"] = subgerencias.apply(
        lambda r: r["Real_Acumulado"] / r["Presupuesto_Total_Anual"] if r["Presupuesto_Total_Anual"] > 0 else None,
        axis=1,
    )
    subgerencias = subgerencias.sort_values("Presupuesto_Total_Anual", ascending=False).reset_index(drop=True)

    evolucion = (
        res_opex_ppto[res_opex_ppto["Mes_Num"] <= ultimo_mes]
        .groupby("Mes_Num", as_index=False)[["Real_Acumulado", "Importe_Real"]].sum()
        .rename(columns={"Importe_Real": "Importe_Real_Mes"})
        .sort_values("Mes_Num")
    )

    det = pd.read_sql_query(
        f"SELECT Cod_SAP, Nombre_Personal, Cargo, Subgerencia, Concepto, Importe, Cantidad_Horas, Ceco "
        f"FROM {TABLE_DETALLE} WHERE Gerencia = :g",
        engine, params={"g": gerencia},
    )
    if det.empty:
        # Filtrar un DataFrame vacio con una mascara booleana tambien vacia
        # le hace perder las columnas a pandas (bug conocido) — con 0 filas
        # da lo mismo Opex que Capex, evitamos el filtrado.
        det_opex = det
        det_capex = det
    else:
        es_opex_det = det["Ceco"].map(_es_opex)
        det_opex = det[es_opex_det]
        det_capex = det[~es_opex_det]

    total_opex = float(det_opex["Importe"].sum())
    conceptos = det_opex.groupby("Concepto", as_index=False)["Importe"].sum().sort_values(
        "Importe", ascending=False
    )
    conceptos["Pct"] = conceptos["Importe"] / total_opex if total_opex else 0.0

    personas = _ranking_por_concepto(det_opex)
    personas_capex = _ranking_por_concepto(det_capex)

    return {
        "gerencia": gerencia,
        "anio": anio,
        "ultimo_mes": ultimo_mes,
        "mes_nombre": MESES_INV[ultimo_mes],
        "presupuesto_anual": presupuesto_anual,
        "real_acumulado": real_acumulado,
        "saldo_disponible": saldo_disponible,
        "pct_ocupado": pct_ocupado,
        "ritmo": ritmo,
        "pct_gastado": pct_gastado,
        "subgerencias": subgerencias,
        "evolucion": evolucion,
        "conceptos": conceptos,
        "personas": personas,
        "personas_capex": personas_capex,
    }


def _fmt_millones(valor: float) -> str:
    return f"${valor / 1_000_000:.1f}M"


def _grafico_evolucion(datos: dict) -> Drawing:
    evol = datos["evolucion"]
    meses = [MESES_INV[m][:3] for m in evol["Mes_Num"]]
    reales = evol["Real_Acumulado"].tolist()
    presupuesto_flat = [datos["presupuesto_anual"]] * len(reales)

    ancho, alto = ANCHO_CONTENIDO, 7.6 * cm
    d = Drawing(ancho, alto)
    chart = HorizontalLineChart()
    chart.x = 1.5 * cm
    chart.y = 1.2 * cm
    chart.width = ancho - 3 * cm
    chart.height = alto - 3.7 * cm
    chart.data = [reales, presupuesto_flat]
    chart.categoryAxis.categoryNames = meses
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labelTextFormat = lambda v: f"${v / 1_000_000:.0f}M"
    chart.valueAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.lines[0].strokeColor = ROJO
    chart.lines[0].strokeWidth = 2
    chart.lines[1].strokeColor = NAVY
    chart.lines[1].strokeWidth = 1.2
    chart.lines[1].strokeDashArray = [4, 3]
    chart.joinedLines = 1
    # Valor sobre cada punto de la linea Real acumulado. La de Presupuesto
    # anual NO lleva valor repetido en cada mes (es el mismo monto fijo las
    # 12 veces) — ese monto se muestra UNA sola vez, centrado arriba del
    # grafico (ver texto "presupuesto anual" mas abajo).
    chart.lineLabelNudge = 7
    chart.lineLabels.fontSize = 6.5
    chart.lineLabels.fillColor = ROJO
    # "values" (string literal, no es un valor cualquiera) le dice a reportlab
    # que use lineLabelArray en vez de un formato/callback global — con
    # lineLabelFormat=None (default) no dibuja NINGUN label, sin importar
    # lineLabelArray.
    chart.lineLabelFormat = "values"
    chart.lineLabelArray = [[_fmt_millones(v) for v in reales], [None] * len(presupuesto_flat)]
    d.add(chart)

    centro_x = chart.x + chart.width / 2

    # Monto de Presupuesto anual, una sola vez, centrado arriba del grafico.
    texto_ppto_y = alto - 0.4 * cm
    d.add(String(
        centro_x, texto_ppto_y,
        f"Presupuesto anual: {_fmt_millones(datos['presupuesto_anual'])}",
        fillColor=NAVY, fontSize=9, fontName="Helvetica-Bold", textAnchor="middle",
    ))

    # Leyenda con muestra de linea real (color + trazo), no con guiones de
    # texto, para no meter guiones dentro del PDF.
    leyenda_y = alto - 0.95 * cm
    x1 = centro_x - 3.6 * cm
    d.add(Line(x1, leyenda_y, x1 + 0.9 * cm, leyenda_y, strokeColor=ROJO, strokeWidth=2))
    d.add(String(x1 + 1.15 * cm, leyenda_y - 3, "Real acumulado", fillColor=NAVY, fontSize=8))

    x2 = centro_x + 0.6 * cm
    linea_navy = Line(x2, leyenda_y, x2 + 0.9 * cm, leyenda_y, strokeColor=NAVY, strokeWidth=1.2)
    linea_navy.strokeDashArray = [4, 3]
    d.add(linea_navy)
    d.add(String(x2 + 1.15 * cm, leyenda_y - 3, "Presupuesto anual", fillColor=NAVY, fontSize=8))
    return d


def _tabla_kpis(datos: dict) -> Table:
    encabezados = ["Presupuesto anual", "Gasto acumulado", "Saldo disponible", "% Ejecutado"]
    valores = [
        _fmt_clp(datos["presupuesto_anual"]),
        _fmt_clp(datos["real_acumulado"]),
        _fmt_clp(datos["saldo_disponible"]),
        _fmt_pct(datos["pct_ocupado"]),
    ]
    color_saldo = ROJO if datos["saldo_disponible"] < 0 else SUCCESS
    t = Table([encabezados, valores], colWidths=[ANCHO_CONTENIDO / 4] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), BLANCO),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 13),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (2, 1), (2, 1), color_saldo),
        ("BACKGROUND", (0, 1), (-1, 1), GRIS_CLARO),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.5, GRIS),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, GRIS),
    ]))
    return t


def _tabla_estado(datos: dict) -> Table:
    nivel = _nivel(datos["pct_gastado"], datos["ritmo"])
    nivel_ritmo = _nivel_ritmo(datos["ritmo"])
    color = NIVEL_COLOR[nivel]

    linea1 = _celda(
        f"Estado general: {NIVEL_LABEL[nivel]}",
        alineacion=TA_CENTER, negrita=True, tamano=11, color=BLANCO,
    )
    linea2 = _celda(
        f"% Gastado: {_fmt_pct(datos['pct_gastado'])}    |    {PROGRESO_LABEL[nivel_ritmo]}",
        alineacion=TA_CENTER, negrita=False, tamano=9, color=BLANCO,
    )
    t = Table([[linea1], [linea2]], colWidths=[ANCHO_CONTENIDO])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (0, 0), 8),
        ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 8),
    ]))
    return t


# Estilo base compartido por las tablas de detalle (encabezado navy + filas
# con cebra + grilla fina). Cada una agrega sus propias colWidths/colores.
_ESTILO_BASE_DETALLE = [
    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("INNERGRID", (0, 0), (-1, -1), 0.4, GRIS),
    ("BOX", (0, 0), (-1, -1), 0.5, GRIS),
]


def _tabla_evolucion_mensual(datos: dict) -> Table:
    """El grafico de Evolucion mensual solo muestra el acumulado (Real
    acumulado vs. Presupuesto anual) — esta tabla agrega el gasto mensual
    puntual (no acumulado) de cada mes, que el grafico no deja ver."""
    encabezados = ["Mes", "Gasto del mes", "Gasto acumulado"]
    filas = [[_celda(h, negrita=True, tamano=8, color=BLANCO, alineacion=TA_CENTER) for h in encabezados]]
    estilo = list(_ESTILO_BASE_DETALLE)
    for i, fila in enumerate(datos["evolucion"].itertuples(), start=1):
        filas.append([
            _celda(MESES_INV[fila.Mes_Num], alineacion=TA_CENTER),
            _celda(_fmt_clp(fila.Importe_Real_Mes), alineacion=TA_RIGHT),
            _celda(_fmt_clp(fila.Real_Acumulado), alineacion=TA_RIGHT),
        ])
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))
    t = Table(filas, colWidths=[6 * cm, 6 * cm, 6 * cm])
    t.setStyle(TableStyle(estilo))
    return t


def _tabla_subgerencias(datos: dict) -> Table:
    encabezados = ["Subgerencia", "Presupuesto anual", "Gasto acumulado", "Saldo", "% Ejec."]
    filas = [[_celda(h, negrita=True, tamano=8, color=BLANCO, alineacion=TA_CENTER) for h in encabezados]]
    estilo = list(_ESTILO_BASE_DETALLE)
    for i, fila in enumerate(datos["subgerencias"].itertuples(), start=1):
        color_saldo = ROJO if fila.Saldo_Disponible < 0 else NAVY
        filas.append([
            _celda(fila.Subgerencia),
            _celda(_fmt_clp(fila.Presupuesto_Total_Anual), alineacion=TA_RIGHT),
            _celda(_fmt_clp(fila.Real_Acumulado), alineacion=TA_RIGHT),
            _celda(_fmt_clp(fila.Saldo_Disponible), alineacion=TA_RIGHT, color=color_saldo),
            _celda(_fmt_pct(fila.Pct_Ocupado), alineacion=TA_RIGHT),
        ])
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))
    t = Table(filas, colWidths=[6.3 * cm, 3.7 * cm, 3.7 * cm, 2.6 * cm, 1.7 * cm])
    t.setStyle(TableStyle(estilo))
    return t


def _tabla_conceptos(datos: dict) -> Table:
    encabezados = ["Concepto", "Monto", "% del total"]
    filas = [[_celda(h, negrita=True, tamano=8, color=BLANCO, alineacion=TA_CENTER) for h in encabezados]]
    estilo = list(_ESTILO_BASE_DETALLE)
    for i, fila in enumerate(datos["conceptos"].itertuples(), start=1):
        filas.append([
            _celda(fila.Concepto),
            _celda(_fmt_clp(fila.Importe), alineacion=TA_RIGHT),
            _celda(_fmt_pct(fila.Pct), alineacion=TA_RIGHT),
        ])
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))
    t = Table(filas, colWidths=[9 * cm, 5 * cm, 4 * cm])
    t.setStyle(TableStyle(estilo))
    return t


def _tabla_ranking(personas: pd.DataFrame) -> Table:
    # Solo columnas de Concepto con al menos un valor != 0 entre las
    # personas mostradas — igual que el ranking del dashboard HTML, para
    # no ocupar espacio con columnas en $0 (ej. Bono Disponibilidad en una
    # Gerencia donde nadie de las Top 10 lo tiene).
    conceptos_visibles = [c for c in CONCEPTOS_RANKING if (personas[c] != 0).any()]

    encabezados = ["#", "Nombre", "Horas"] + [LABEL_CONCEPTO_CORTO.get(c, c) for c in conceptos_visibles] + ["Total"]
    filas = [[_celda(h, negrita=True, tamano=7.5, color=BLANCO, alineacion=TA_CENTER) for h in encabezados]]
    estilo = list(_ESTILO_BASE_DETALLE)
    for i, (_, fila) in enumerate(personas.iterrows(), start=1):
        celdas = [
            _celda(str(i), alineacion=TA_CENTER),
            _celda(fila["Nombre_Personal"], tamano=7.5),
            _celda(f"{fila['Horas']:.1f}", alineacion=TA_RIGHT, tamano=7.5),
        ]
        for concepto in conceptos_visibles:
            celdas.append(_celda(_fmt_clp(fila[concepto]), alineacion=TA_RIGHT, tamano=7.5))
        celdas.append(_celda(_fmt_clp(fila["Total"]), alineacion=TA_RIGHT, negrita=True, tamano=7.5))
        filas.append(celdas)
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), GRIS_CLARO))

    ancho_num = 0.7 * cm
    ancho_nombre = 4.8 * cm
    ancho_horas = 1.5 * cm
    ancho_total = 2.4 * cm
    ancho_concepto = (
        (ANCHO_CONTENIDO - ancho_num - ancho_nombre - ancho_horas - ancho_total)
        / max(len(conceptos_visibles), 1)
    )
    col_widths = [ancho_num, ancho_nombre, ancho_horas] + [ancho_concepto] * len(conceptos_visibles) + [ancho_total]

    t = Table(filas, colWidths=col_widths)
    t.setStyle(TableStyle(estilo))
    return t


GENERADO_POR = "Equipo de Compensaciones"


def _pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#6a6c6e"))
    canvas.drawString(1.5 * cm, 1.2 * cm, "Documento de uso interno. No distribuir.")
    canvas.drawRightString(A4[0] - 1.5 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _construir_pdf(datos: dict, output_path: Path) -> None:
    styles = {
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=16, textColor=NAVY, spaceAfter=8, alignment=TA_CENTER),
        "subtitulo": ParagraphStyle("subtitulo", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#373b53"), spaceAfter=5, alignment=TA_CENTER),
        "meta": ParagraphStyle("meta", fontName="Helvetica-Oblique", fontSize=7.5, textColor=colors.HexColor("#6a6c6e"), spaceBefore=3, alignment=TA_CENTER),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, textColor=NAVY, spaceBefore=14, spaceAfter=6),
        "nota": ParagraphStyle("nota", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#6a6c6e")),
    }

    def seccion(texto: str) -> list:
        """Titulo de seccion + linea divisoria roja debajo, para separar
        secciones con mas fuerza visual (similar a los "cards" con header
        del dashboard HTML)."""
        return [
            Paragraph(texto, styles["h2"]),
            HRFlowable(width="100%", thickness=1.3, color=ROJO, spaceBefore=0, spaceAfter=8),
        ]

    generado_el = datetime.now().strftime("%d-%m-%Y, %H:%M:%S")
    titulo_texto = f'Informe de Sobretiempo {_esc(datos["gerencia"])}'

    bloque_titulo = [
        Paragraph(titulo_texto, styles["titulo"]),
        Paragraph(f"Gasto a {datos['mes_nombre']} {datos['anio']}", styles["subtitulo"]),
        Paragraph(f"Generado el {generado_el} por {GENERADO_POR}. Documento confidencial, uso interno.", styles["meta"]),
    ]
    logo = _logo_flowable()
    if logo is not None:
        logo.hAlign = "CENTER"
    # Logo arriba del titulo (no al costado), centrado, tipo membrete
    # corporativo.
    encabezado_flowables = ([logo, Spacer(1, 8)] if logo is not None else []) + bloque_titulo

    # Cada seccion (titulo + divisoria + contenido) va envuelta en
    # KeepTogether: si no entra completa en lo que queda de la pagina
    # actual, reportlab la pasa entera a la pagina siguiente en vez de
    # cortarla a mitad de tabla/grafico — a pedido del usuario.
    story = [
        *encabezado_flowables,
        Spacer(1, 12),
        _tabla_kpis(datos),
        Spacer(1, 10),
        KeepTogether([
            *seccion("Estado"),
            _tabla_estado(datos),
            Paragraph(
                "El Estado general combina dos indicadores: % Gastado (ejecución acumulada a la fecha) y "
                "Progreso de gasto (ritmo actual proyectado a fin de año).",
                styles["nota"],
            ),
        ]),
        KeepTogether([
            *seccion("Evolución mensual"),
            _grafico_evolucion(datos),
            Spacer(1, 6),
            _tabla_evolucion_mensual(datos),
        ]),
    ]

    if len(datos["subgerencias"]) > 1:
        story.append(Spacer(1, 4))
        story.append(KeepTogether([
            *seccion("Desglose por Subgerencia"),
            _tabla_subgerencias(datos),
        ]))

    if not datos["conceptos"].empty:
        story.append(Spacer(1, 4))
        story.append(KeepTogether([
            *seccion("Gasto por Concepto"),
            _tabla_conceptos(datos),
        ]))

    if not datos["personas"].empty:
        story.append(Spacer(1, 4))
        story.append(KeepTogether([
            *seccion("Ranking de Colaboradores con mayores gastos"),
            _tabla_ranking(datos["personas"]),
        ]))

    if not datos["personas_capex"].empty:
        story.append(Spacer(1, 4))
        story.append(KeepTogether([
            *seccion("Ranking Capex"),
            Paragraph(
                "Gasto en centros de costo Capex (fuera del alcance Opex de este informe). "
                "Esto es solo información complementaria.",
                styles["nota"],
            ),
            Spacer(1, 6),
            _tabla_ranking(datos["personas_capex"]),
        ]))

    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.8 * cm,
        title=f"Informe de Sobretiempo: {datos['gerencia']}",
    )
    doc.build(story, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)


def _slug(texto: str) -> str:
    import re
    s = texto.strip().lower()
    s = (s.replace("á", "a").replace("é", "e").replace("í", "i")
         .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "gerencia"


def generar_informes_gerencia(output_dir: Path | None = None) -> list[Path]:
    """Genera un PDF ejecutivo por cada Gerencia con datos cargados.

    No requiere el backend corriendo, lee directo la base SQLite. Devuelve
    la lista de rutas de los PDF generados (una por Gerencia con al menos
    un mes cerrado en sobretiempo_resumen_gerencia).
    """
    destino = output_dir or REPORTES_DIR
    destino.mkdir(parents=True, exist_ok=True)

    generados = []
    for gerencia in _listar_gerencias():
        datos = _datos_gerencia(gerencia)
        if datos is None:
            continue
        # Prefijo en el nombre del archivo para identificar casos especiales
        # a simple vista en el explorador de archivos, sin abrir cada PDF:
        #   "(Sin gasto)" si la Gerencia no tiene NADA de gasto acumulado.
        #   "(Alerta)" si el Ritmo de gasto es >= 1.0x (advertencia o critico).
        if datos["real_acumulado"] == 0:
            prefijo = "(Sin gasto) "
        elif _nivel_ritmo(datos["ritmo"]) != "ok":
            prefijo = "(Alerta) "
        else:
            prefijo = ""
        nombre = f"{prefijo}Sobretiempo_{_slug(gerencia)}_{datos['mes_nombre']}_{datos['anio']}.pdf"
        ruta = destino / nombre
        try:
            _construir_pdf(datos, ruta)
        except PermissionError:
            # Pasa si el PDF anterior quedo abierto en un visor (Edge,
            # Acrobat, etc.) — Windows bloquea la escritura. Se salta esa
            # Gerencia en vez de cortar toda la corrida; el usuario cierra
            # el visor y corre el script de nuevo para esa Gerencia.
            print(f"  (omitido, archivo abierto en otro programa): {ruta}")
            continue
        generados.append(ruta)
    return generados
