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


def _tabla_a_json(tabla: str, columnas_bool: list[str]) -> str:
    df = pd.read_sql_query(f"SELECT * FROM {tabla}", engine)
    for col in columnas_bool:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    return df.to_json(orient="records")


def generar_reporte_html(output_path: Path | None = None) -> Path:
    """Genera el HTML autocontenido de Sobretiempo y lo guarda en disco.

    No requiere el backend corriendo — lee frontend/dist del disco y
    consulta la base SQLite directamente. Devuelve la ruta del archivo
    generado.
    """
    js, css = _leer_assets_build()
    resumen_json = _tabla_a_json(TABLE_RESUMEN, COLUMNAS_BOOL_RESUMEN)
    detalle_json = _tabla_a_json(TABLE_DETALLE, COLUMNAS_BOOL_DETALLE)

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
        output_path = REPORTES_DIR / f"sobretiempo_{ahora.strftime('%Y-%m-%d_%H%M%S')}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
