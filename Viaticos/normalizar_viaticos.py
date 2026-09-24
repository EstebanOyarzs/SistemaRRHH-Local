"""
================================================================================
NORMALIZADOR DE VIATICOS -> EXCEL LIMPIO
================================================================================
Lee el Excel bruto "Informe_VI_<Mes><Año>.xlsx" (hoja "Detalle 2026", tal como
lo exporta SAP) y escribe una version limpia, lista para reportar, en
Viaticos/data/Detalle_Normalizado.xlsx.

Mismo patron de dos pasos "normalizar -> generar reporte" que usan los demas
dashboards del proyecto (Sobretiempo, Capacitacion) -- la diferencia es que
Viaticos no tiene base de datos propia (mismo criterio que Geovictoria, sin
backend), asi que el paso intermedio es un Excel normalizado en vez de una
tabla SQLite. `generar_reporte_viaticos.py` lee ese Excel, nunca el bruto
directamente.

USO CADA MES:
    venv\\Scripts\\python.exe Viaticos\\normalizar_viaticos.py "ruta\\al\\nuevo_Informe_VI.xlsx"

Si no se indica ruta, usa el Excel de ejemplo en "Archivos\\Informe_VI_Agosto2026.xlsx".
================================================================================
"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
EJEMPLO = PROJECT_ROOT / "Archivos" / "Informe_VI_Agosto2026.xlsx"
SALIDA_NORMALIZADO = PROJECT_ROOT / "data" / "Detalle_Normalizado.xlsx"

HOJA_DETALLE = "Detalle 2026"
HOJA_SALIDA = "Detalle"

COLUMNAS_USO = [
    "NUMERO", "Documento SAP", "Fecha viatico", "Mes", "Año", "Sociedad", "Rut", "Nombre",
    "Gerencia", "Sub-gerencia", "Aprobador", "Valor importe", "Cuenta",
]


def normalizar_excel(ruta_excel: Path) -> pd.DataFrame:
    df = pd.read_excel(ruta_excel, sheet_name=HOJA_DETALLE, engine="openpyxl")
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df[COLUMNAS_USO].copy()
    df = df.dropna(subset=["Fecha viatico", "Valor importe"])

    for col in ("Sociedad", "Nombre", "Gerencia", "Sub-gerencia", "Aprobador", "Rut"):
        df[col] = df[col].astype(str).str.strip()

    # Cuando "Sub-gerencia" repite el mismo texto que "Gerencia", el registro
    # no tiene una subgerencia real asignada (reporta directo a la Gerencia).
    df["Sub-gerencia"] = df.apply(
        lambda r: "(Sin subgerencia)" if r["Sub-gerencia"] == r["Gerencia"] else r["Sub-gerencia"],
        axis=1,
    )

    df["Fecha viatico"] = pd.to_datetime(df["Fecha viatico"]).dt.date
    df["NUMERO"] = df["NUMERO"].astype(int)
    df["Documento SAP"] = df["Documento SAP"].astype(int)
    df["Cuenta"] = df["Cuenta"].astype(int)
    df["Valor importe"] = df["Valor importe"].astype(float).round().astype(int)
    return df


def normalizar(ruta_excel: Path, destino: Path | None = None) -> Path:
    df = normalizar_excel(ruta_excel)
    destino = destino or SALIDA_NORMALIZADO
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(destino, index=False, sheet_name=HOJA_SALIDA)
    return destino


def main(archivo=None, salida=None):
    ruta = Path(archivo) if archivo else EJEMPLO
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro el archivo Excel: {ruta}")
    destino = Path(salida) if salida else None
    resultado = normalizar(ruta, destino)
    df = pd.read_excel(resultado, sheet_name=HOJA_SALIDA)
    print(f"Normalizado: {len(df):,} filas")
    print(f"Guardado en: {resultado}")


if __name__ == "__main__":
    arg_archivo = sys.argv[1] if len(sys.argv) > 1 else None
    arg_salida = sys.argv[2] if len(sys.argv) > 2 else None
    main(arg_archivo, arg_salida)
