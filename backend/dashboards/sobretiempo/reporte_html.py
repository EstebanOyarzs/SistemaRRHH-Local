"""
================================================================================
GENERADOR DE REPORTE HTML DE SOBRETIEMPO (sin servidor)
================================================================================
Arma el MISMO archivo autocontenido que el boton "Descargar reporte (HTML)"
del dashboard (ver frontend/src/utils/exportarHtml.ts) — mismo bundle JS/CSS
de produccion + los datos completos embebidos — pero leyendo todo directo del
disco y la base SQLite, sin necesitar el backend corriendo ni abrir ningun
puerto de red.

Pensado como respaldo cuando no se puede mantener uvicorn levantado (ver
Sobretiempo/generar_reporte_sobretiempo.py para el uso de linea de comandos).
Requiere que frontend/dist ya este compilado (`vite build`).
"""

import getpass
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from backend.config import PROJECT_ROOT
from backend.dashboards.sobretiempo.db import TABLE_DETALLE, TABLE_RESUMEN, engine
from backend.dashboards.sobretiempo.normalizar import MESES_INV

DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
REPORTES_DIR = PROJECT_ROOT / "Sobretiempo" / "data" / "reportes"

# Mismas columnas booleanas que declara backend/dashboards/sobretiempo/schemas.py
# (Optional[bool]) — al leerlas crudas de SQLite via pandas vienen como 0/1,
# hay que castearlas para que el JSON embebido tenga true/false de verdad,
# igual que devuelve la API real (FastAPI serializa el response_model Pydantic).
COLUMNAS_BOOL_RESUMEN = ["Mes_Cerrado", "Con_Presupuesto_Asignado"]
COLUMNAS_BOOL_DETALLE = ["Mes_Cerrado", "Con_Presupuesto_Asignado"]


def _escapar_cierre(texto: str, tag: str) -> str:
    """Evita que datos/código con la secuencia literal '</tag' corten el
    elemento antes de tiempo al insertarlo como texto plano en el HTML."""
    return re.sub(f"</{tag}", f"<\\/{tag}", texto, flags=re.IGNORECASE)


def _leer_assets_build():
    index_html = DIST_DIR / "index.html"
    if not index_html.exists():
        raise FileNotFoundError(
            f"No se encontro {index_html}. Hay que compilar el frontend primero: "
            'cd frontend; node ".\\node_modules\\vite\\bin\\vite.js" build'
        )
    contenido = index_html.read_text(encoding="utf-8")

    match_js = re.search(r'<script[^>]+src="(/assets/[^"]+\.js)"', contenido)
    match_css = re.search(r'<link[^>]+href="(/assets/[^"]+\.css)"', contenido)
    if not match_js or not match_css:
        raise ValueError(f"No se pudieron ubicar los tags de script/css en {index_html}")

    js_path = DIST_DIR / match_js.group(1).lstrip("/")
    css_path = DIST_DIR / match_css.group(1).lstrip("/")
    return js_path.read_text(encoding="utf-8"), css_path.read_text(encoding="utf-8")


def _tabla_a_json(df: pd.DataFrame, columnas_bool: list[str]) -> str:
    df = df.copy()
    for col in columnas_bool:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    return df.to_json(orient="records")


def _ultimo_mes_anio(df_resumen: pd.DataFrame) -> tuple[str | None, int | None]:
    """Mes (nombre) y año del último mes cerrado en los datos — para
    nombrar el archivo exportado con el mes al que corresponde (ej.
    "Junio_2026"), no solo con la fecha/hora de generación."""
    cerrado = df_resumen[df_resumen["Mes_Cerrado"] == 1]
    if cerrado.empty:
        return None, None
    ultimo_mes = int(cerrado["Mes_Num"].max())
    anio = int(cerrado["Anio"].dropna().iloc[0])
    return MESES_INV[ultimo_mes], anio


def generar_reporte_html(output_path: Path | None = None) -> Path:
    """Genera el HTML autocontenido de Sobretiempo y lo guarda en disco.

    No requiere el backend corriendo — lee frontend/dist del disco y
    consulta la base SQLite directamente. Devuelve la ruta del archivo
    generado.
    """
    js, css = _leer_assets_build()
    df_resumen = pd.read_sql_query(f"SELECT * FROM {TABLE_RESUMEN}", engine)
    df_detalle = pd.read_sql_query(f"SELECT * FROM {TABLE_DETALLE}", engine)
    resumen_json = _tabla_a_json(df_resumen, COLUMNAS_BOOL_RESUMEN)
    detalle_json = _tabla_a_json(df_detalle, COLUMNAS_BOOL_DETALLE)
    mes_nombre, anio = _ultimo_mes_anio(df_resumen)

    ahora = datetime.now()
    generado_el = ahora.strftime("%d-%m-%Y, %H:%M:%S")
    try:
        generado_por = getpass.getuser()
    except Exception:
        generado_por = None

    payload = (
        '{"resumenCompleto":' + resumen_json +
        ',"detalleCompleto":' + detalle_json +
        ',"generadoEl":"' + generado_el + '"' +
        ',"generadoPor":' + json.dumps(generado_por) +
        '}'
    )
    payload = _escapar_cierre(payload, "script")
    js_seguro = _escapar_cierre(js, "script")
    css_segura = _escapar_cierre(css, "style")

    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Sobretiempo - reporte exportado</title>
<style>{css_segura}</style>
</head>
<body>
<div id="root"></div>
<script>window.__PDA_EXPORT__ = {payload};</script>
<script type="module">{js_seguro}</script>
</body>
</html>
"""

    if output_path is None:
        REPORTES_DIR.mkdir(parents=True, exist_ok=True)
        # Nombre incluye el mes de los datos (ej. "Junio_2026"), ademas del
        # timestamp de generacion — el reporte se puede generar meses
        # despues del cierre de los datos, asi que la fecha de generacion
        # sola no dice a que mes corresponde el contenido.
        sufijo_mes = f"{mes_nombre}_{anio}_" if mes_nombre and anio else ""
        output_path = REPORTES_DIR / f"Sobretiempo_{sufijo_mes}{ahora.strftime('%Y-%m-%d_%H%M%S')}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
