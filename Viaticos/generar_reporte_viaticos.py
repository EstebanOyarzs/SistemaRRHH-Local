"""
================================================================================
GENERADOR DE REPORTE HTML DE VIATICOS
================================================================================
Lee el Excel YA NORMALIZADO (Viaticos/data/Detalle_Normalizado.xlsx, generado
por normalizar_viaticos.py -- nunca el Excel bruto de SAP directamente) y
genera un reporte HTML autocontenido (datos + Chart.js embebidos, sin
necesitar servidor ni conexion a internet para abrirlo), siguiendo el mismo
patron visual del dashboard de Sobretiempo/GeoVictoria pero en tonos
verde/teal + navy.

No hay hoja de presupuesto en este Excel (a diferencia de Sobretiempo): el
reporte es de gasto real de viaticos, sin comparacion contra PPTO.

USO (primero normalizar, despues generar el reporte):
    venv\\Scripts\\python.exe Viaticos\\normalizar_viaticos.py "ruta\\al_Informe_VI.xlsx"
    venv\\Scripts\\python.exe Viaticos\\generar_reporte_viaticos.py
    venv\\Scripts\\python.exe Viaticos\\generar_reporte_viaticos.py "ruta\\normalizado.xlsx" "ruta\\salida.html"

Si no se pasa archivo, usa Viaticos/data/Detalle_Normalizado.xlsx.
================================================================================
"""

import base64
import json
import sys
from pathlib import Path

import pandas as pd
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
NORMALIZADO = PROJECT_ROOT / "data" / "Detalle_Normalizado.xlsx"
LOGO_PATH = PROJECT_ROOT / "logo.png"
CHARTJS_PATH = (
    PROJECT_ROOT.parent
    / "frontend"
    / "node_modules"
    / "chart.js"
    / "dist"
    / "chart.umd.min.js"
)
CHARTJS_DATALABELS_PATH = (
    PROJECT_ROOT.parent
    / "frontend"
    / "node_modules"
    / "chartjs-plugin-datalabels"
    / "dist"
    / "chartjs-plugin-datalabels.min.js"
)

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

GENERADO_POR = "Eoyarzun"

HOJA_NORMALIZADO = "Detalle"


def cargar_datos(ruta_normalizado: Path) -> pd.DataFrame:
    # El archivo ya viene limpio (columnas, tipos, "(Sin subgerencia)")
    # desde normalizar_viaticos.py -- aca solo se lee y se deriva Fecha_dt.
    df = pd.read_excel(ruta_normalizado, sheet_name=HOJA_NORMALIZADO, engine="openpyxl")
    df["Fecha_dt"] = pd.to_datetime(df["Fecha viatico"]).dt.date
    df["Valor importe"] = df["Valor importe"].astype(float)
    return df


def _mapa_ids(df: pd.DataFrame) -> dict:
    # Igual criterio que Geovictoria: el RUT nunca se escribe en el HTML (el
    # reporte es un archivo estatico que puede circular fuera del sistema),
    # pero se necesita para agrupar por colaborador sin arriesgar fusionar a
    # dos personas distintas con el mismo nombre (Nombre no es unico en teoria,
    # aunque en estos datos si lo es 1 a 1 con Rut).
    ruts = sorted(df["Rut"].dropna().unique())
    return {rut: idx + 1 for idx, rut in enumerate(ruts)}


def construir_datos_reporte(df: pd.DataFrame) -> dict:
    mapa_id = _mapa_ids(df)

    filas = [
        {
            "id": mapa_id[r["Rut"]],
            "no": int(r["NUMERO"]),
            "sap": int(r["Documento SAP"]),
            "f": r["Fecha_dt"].isoformat(),
            "n": r["Nombre"],
            "g": r["Gerencia"],
            "sg": r["Sub-gerencia"],
            "s": r["Sociedad"],
            "ap": r["Aprobador"],
            "v": round(float(r["Valor importe"])),
            "ct": int(r["Cuenta"]),
        }
        for _, r in df.iterrows()
    ]

    gerencias = sorted(df["Gerencia"].dropna().unique().tolist())
    subgerencias = sorted(df["Sub-gerencia"].dropna().unique().tolist())
    sociedades = sorted(df["Sociedad"].dropna().unique().tolist())
    aprobadores = sorted(df["Aprobador"].dropna().unique().tolist())
    nombres = sorted(df["Nombre"].dropna().unique().tolist())
    meses_pares = sorted({(f.year, f.month) for f in df["Fecha_dt"]})
    meses = [f"{MESES[m]} {y}" for (y, m) in meses_pares]

    fecha_min = min(df["Fecha_dt"])
    fecha_max = max(df["Fecha_dt"])

    return {
        "fecha_min": fecha_min.isoformat(),
        "fecha_max": fecha_max.isoformat(),
        "filas": filas,
        "opciones": {
            "gerencias": gerencias,
            "subgerencias": subgerencias,
            "sociedades": sociedades,
            "aprobadores": aprobadores,
            "nombres": nombres,
            "meses": meses,
        },
    }


def _periodo(df: pd.DataFrame) -> str:
    fmin, fmax = min(df["Fecha_dt"]), max(df["Fecha_dt"])
    if (fmin.year, fmin.month) == (fmax.year, fmax.month):
        return f"{MESES[fmax.month]} {fmax.year}"
    if fmin.year == fmax.year:
        return f"{MESES[fmin.month]} - {MESES[fmax.month]} {fmax.year}"
    return f"{MESES[fmin.month]} {fmin.year} - {MESES[fmax.month]} {fmax.year}"


def _nombre_archivo(df: pd.DataFrame) -> str:
    fmax = max(df["Fecha_dt"])
    return f"Control_de_Viaticos_{MESES[fmax.month]}_{fmax.year}"


HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Control de Viaticos - {periodo}</title>
<style>
{estilos}
</style>
</head>
<body>
<div class="via">
  <header class="via__header">
    <div class="via__title">
      {logo_html}
      <div>
        <h1>Control de Viaticos</h1>
        <p class="via__subtitle">Gasto acumulado - {periodo}</p>
      </div>
    </div>
    <div class="via__meta">
      <span>Datos del {fecha_min} al {fecha_max}</span>
      <span>Generado el {generado_el} por {generado_por}</span>
      <span class="via__meta-destacado">Gerencia de Personas</span>
    </div>
  </header>

  <div class="via__filtros" id="filtros">
    <div class="via__filtros-grupo" id="filtro-gerencia"></div>
    <div class="via__filtros-grupo" id="filtro-subgerencia"></div>
    <div class="via__filtros-grupo" id="filtro-sociedad"></div>
    <div class="via__filtros-grupo" id="filtro-aprobador"></div>
    <div class="via__filtros-grupo" id="filtro-nombre"></div>
    <div class="via__filtros-grupo" id="filtro-mes"></div>
    <button class="via__filtros-limpiar" id="btn-limpiar-filtros" type="button">Limpiar filtros</button>
  </div>

  <section>
    <h2>Resumen</h2>
    <div class="card">
      <div class="kpis" id="kpis"></div>
    </div>
  </section>

  <section>
    <h2>Evolucion mensual</h2>
    <div class="card">
      <div class="via__chart"><canvas id="chart-evolucion"></canvas></div>
    </div>
  </section>

  <section>
    <div class="via__panel-grid">
      <div class="card">
        <h3>Gasto por Gerencia</h3>
        <div class="via__chart-scroll via__chart-scroll--rows10">
          <div class="via__chart-inner" id="chart-gerencia-inner"><canvas id="chart-gerencia"></canvas></div>
        </div>
      </div>
      <div class="card">
        <h3>Gasto por Sub-gerencia</h3>
        <div class="via__chart-scroll via__chart-scroll--rows10">
          <div class="via__chart-inner" id="chart-subgerencia-inner"><canvas id="chart-subgerencia"></canvas></div>
        </div>
      </div>
    </div>
  </section>

  <section>
    <h2>Ranking de colaboradores</h2>
    <div class="card via__table-card">
      <div class="via__table-wrap via__table-wrap--scroll via__table-wrap--rows15">
        <table id="tabla-ranking">
          <thead><tr>
            <th data-key="nombre" data-tipo="str">Nombre</th>
            <th data-key="total" data-tipo="num">Total</th>
            <th data-key="n_viaticos" data-tipo="num">N. viaticos</th>
            <th data-key="gerencia" data-tipo="str">Gerencia</th>
            <th data-key="subgerencia" data-tipo="str">Sub-gerencia</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>

  <section>
    <h2>Alertas</h2>
    <p class="via__subtitle">Las alertas son del ultimo mes en comparacion al promedio historico, por lo que aplican todos los filtros, exceptuando "Mes".</p>
    <div class="card">
      <div class="alerta-resumen" id="alerta-resumen">
        <span class="alerta-resumen__num" id="alerta-resumen-num">0</span>
        <span class="alerta-resumen__texto" id="alerta-resumen-texto"></span>
      </div>
    </div>
    <div class="card via__table-card">
      <h3>Colaboradores con salto mensual</h3>
      <p class="via__alerta-nota">Monto del ultimo mes vs. su promedio de gasto en meses anteriores con viatico. Semaforo: <span class="badge-nivel badge-nivel--moderado">50%+</span> <span class="badge-nivel badge-nivel--alto">80%+</span> <span class="badge-nivel badge-nivel--muyalto">100%+</span></p>
      <div class="via__table-wrap via__table-wrap--scroll via__table-wrap--rows10">
        <table id="tabla-alerta-persona" class="via__table-fixed via__table-fixed--persona">
          <thead><tr>
            <th data-key="nivel" data-tipo="nivel">Nivel</th>
            <th data-key="nombre" data-tipo="str">Nombre</th>
            <th data-key="sociedad" data-tipo="str">Sociedad</th>
            <th data-key="promedio_gasto" data-tipo="num">Promedio</th>
            <th data-key="monto_ultimo" data-tipo="num">Ultimo mes</th>
            <th data-key="aumento_pct" data-tipo="num">Aumento</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
    <div class="via__panel-grid via__panel-grid--alertas">
      <div class="card via__table-card">
        <h3>Gerencias con salto mensual</h3>
        <p class="via__alerta-nota">Monto del ultimo mes vs. el promedio de gasto en meses anteriores. Umbral: aumento de 50% o mas.</p>
        <div class="via__table-wrap via__table-wrap--scroll via__table-wrap--rows10">
          <table id="tabla-alerta-gerencia">
            <thead><tr>
              <th data-key="gerencia" data-tipo="str">Gerencia</th>
              <th data-key="promedio_anterior" data-tipo="num">Promedio</th>
              <th data-key="monto_ultimo" data-tipo="num">Monto ultimo mes</th>
              <th data-key="aumento_pct" data-tipo="num">Aumento</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
      <div class="card via__table-card">
        <h3>Concentracion por Aprobador</h3>
        <p class="via__alerta-nota">Ranking de Aprobadores por monto autorizado, sobre el total de la vista filtrada actual (Gerencia, Sub-gerencia, etc. si estan aplicados arriba).</p>
        <div class="via__table-wrap via__table-wrap--scroll via__table-wrap--rows10">
          <table id="tabla-alerta-aprobador">
            <thead><tr>
              <th data-key="aprobador" data-tipo="str">Aprobador</th>
              <th data-key="pct" data-tipo="num">% del total</th>
              <th data-key="monto" data-tipo="num">Monto</th>
              <th data-key="n_viaticos" data-tipo="num">N. viaticos</th>
            </tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <section>
    <h2>Detalle</h2>
    <div class="card via__table-card">
      <div class="via__table-wrap via__table-wrap--scroll via__table-wrap--rows15">
        <table id="tabla-detalle">
          <thead><tr>
            <th data-key="numero" data-tipo="num">Numero</th>
            <th data-key="documento_sap" data-tipo="num">Documento SAP</th>
            <th data-key="fecha" data-tipo="str">Fecha viatico</th>
            <th data-key="nombre" data-tipo="str">Nombre</th>
            <th data-key="importe" data-tipo="num">Importe</th>
            <th data-key="gerencia" data-tipo="str">Gerencia</th>
            <th data-key="subgerencia" data-tipo="str">Sub-gerencia</th>
            <th data-key="aprobador" data-tipo="str">Aprobador</th>
            <th data-key="sociedad" data-tipo="str">Sociedad</th>
            <th data-key="mes" data-tipo="str">Mes</th>
            <th data-key="cuenta" data-tipo="num">Cuenta</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>
</div>

<script>
{chartjs}
</script>
<script>
{chartjs_datalabels}
</script>
<script>
window.__DATA__ = {datos_json};
{app_js}
</script>
</body>
</html>
"""

ESTILOS = """
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap');
:root {
  --color-teal: #0f9d80;
  --color-teal-dark: #0b7a63;
  --color-teal-light: #5bc9ae;
  --color-navy: #17293b;
  --color-navy-light: #3a4f63;
  --color-gray-bg: #f3f8f6;
  --color-gray-bg-alt: #e7f4ef;
  --color-gray-border: #dbe5e1;
  --color-gray-text: #5b6b66;
  --color-white: #ffffff;
  --color-success: #0f9d80;
  --color-danger: #d1483a;
  --font-family: "Nunito", "Segoe UI", sans-serif;
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-pill: 32px;
  --shadow-card: 0 4px 14px rgba(15, 157, 128, 0.1);
}
* { box-sizing: border-box; }
body { margin: 0; font-family: var(--font-family); background: var(--color-gray-bg); color: var(--color-navy); }
h1, h2, h3 { font-weight: 800; margin: 0 0 .5rem; }
.via { display: flex; flex-direction: column; gap: 2rem; padding: 1.5rem 2rem 3rem; max-width: 1400px; margin: 0 auto; }
.via__header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  padding: 1.5rem 1.75rem; margin: -0.5rem -0.5rem 0; border-radius: var(--radius-md);
  background:
    radial-gradient(110% 140% at 0% -10%, rgba(15, 157, 128, 0.14), rgba(255, 255, 255, 0) 60%),
    radial-gradient(90% 140% at 100% -10%, rgba(23, 41, 59, 0.10), rgba(255, 255, 255, 0) 55%),
    var(--color-white);
  box-shadow: var(--shadow-card);
}
.via__title { display: flex; align-items: center; gap: .6rem; }
.via__pin { flex: 0 0 auto; object-fit: contain; border-radius: 10px; }
.via__subtitle { color: var(--color-gray-text); margin: 0; font-weight: 600; }
.via__meta { display: flex; flex-direction: column; gap: .2rem; font-size: .82rem; color: var(--color-gray-text); text-align: right; }
.via__meta-destacado { font-size: 1rem; font-weight: 700; color: var(--color-navy); margin-top: .15rem; }
.via section h2 { border-left: 8px solid var(--color-teal); border-radius: 3px; padding-left: .6rem; margin-bottom: 1rem; }
.card { background: var(--color-white); border-radius: var(--radius-md); box-shadow: var(--shadow-card); padding: 1.25rem 1.5rem; border: 1px solid var(--color-gray-border); }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; }
.kpi { background: var(--color-gray-bg-alt); border-radius: var(--radius-sm); padding: .9rem 1rem; display: flex; flex-direction: column; }
.kpi .label { font-size: .72rem; line-height: 1.35; color: var(--color-gray-text); font-weight: 700; text-transform: uppercase; letter-spacing: .03em; margin-bottom: .4rem; min-height: 1.95em; display: flex; align-items: flex-end; }
.kpi .value { font-size: 1.5rem; font-weight: 800; color: var(--color-navy); margin-top: auto; }
.kpi .value.acento { color: var(--color-teal-dark); }
.via__panel-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1rem; }
.via__panel-grid .card h3 { font-size: .95rem; color: var(--color-navy); margin-bottom: .75rem; }
.via__chart { height: 320px; position: relative; }
.via__chart-scroll { overflow-y: auto; overflow-x: hidden; }
.via__chart-scroll--rows10 { height: 380px; }
.via__chart-inner { position: relative; width: 100%; height: 380px; }
.via__table-wrap { overflow-x: auto; }
.via__table-wrap--scroll { overflow-y: auto; }
.via__table-wrap--scroll thead th { position: sticky; top: 0; background: var(--color-white); z-index: 1; }
.via__table-wrap--rows10 { max-height: 380px; }
.via__table-wrap--rows15 { max-height: 560px; }
.via__table-card { margin-top: 0; }
.via__alerta-nota { margin: 0 0 .75rem; font-size: .78rem; color: var(--color-gray-text); }
.via section > * + * { margin-top: 1.25rem; }
.alerta-resumen {
  display: flex; align-items: center; gap: .9rem; flex-wrap: wrap;
  background: linear-gradient(90deg, rgba(209, 72, 58, .12), rgba(15, 157, 128, .08));
  border: 1px solid rgba(209, 72, 58, .3); border-radius: var(--radius-sm);
  padding: .9rem 1.1rem;
}
.alerta-resumen__num { font-size: 1.9rem; font-weight: 800; color: var(--color-danger); line-height: 1; white-space: nowrap; }
.alerta-resumen__texto { font-size: .88rem; color: var(--color-navy); font-weight: 600; }
.badge-nivel { display: inline-block; padding: .2rem .65rem; border-radius: var(--radius-pill); font-weight: 700; font-size: .78rem; white-space: nowrap; }
.badge-nivel--muyalto { background: var(--color-danger); color: #ffffff; }
.badge-nivel--alto { background: rgba(209, 72, 58, .16); color: var(--color-danger); }
.badge-nivel--moderado { background: rgba(245, 166, 35, .2); color: #8a6100; }
.row-nivel--muyalto { background: rgba(209, 72, 58, .1); }
.row-nivel--alto { background: rgba(209, 72, 58, .05); }
.row-nivel--moderado { background: rgba(245, 166, 35, .08); }
/* Columnas de ancho proporcional (no auto) para que estas tablas quepan
   completas sin scroll horizontal -- Nombre se trunca con "..." en vez de
   forzar el ancho de la tabla. */
.via__table-fixed { table-layout: fixed; }
.via__table-fixed th, .via__table-fixed td { padding: .4rem .5rem; font-size: .78rem; }
.via__table-fixed th:nth-child(1), .via__table-fixed td:nth-child(1) { width: 15%; }
.via__table-fixed th:nth-child(2), .via__table-fixed td:nth-child(2) { width: 29%; overflow: hidden; text-overflow: ellipsis; }
.via__table-fixed th:nth-child(3), .via__table-fixed td:nth-child(3) { width: 10%; }
.via__table-fixed th:nth-child(4), .via__table-fixed td:nth-child(4) { width: 16%; }
.via__table-fixed th:nth-child(5), .via__table-fixed td:nth-child(5) { width: 17%; }
.via__table-fixed th:nth-child(6), .via__table-fixed td:nth-child(6) { width: 13%; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
thead th { text-align: left; color: var(--color-gray-text); font-weight: 700; padding: .5rem .6rem; border-bottom: 2px solid var(--color-gray-border); white-space: nowrap; cursor: pointer; user-select: none; }
thead th:hover { color: var(--color-teal-dark); }
thead th.sorted::after { content: " \\25BC"; font-size: .7rem; color: var(--color-teal); }
thead th.sorted.asc::after { content: " \\25B2"; }
tbody td { padding: .5rem .6rem; border-bottom: 1px solid var(--color-gray-border); white-space: nowrap; }
tbody tr:hover { background: var(--color-gray-bg-alt); }

/* Barra de filtros: fija arriba al hacer scroll, aplica a todo el reporte */
.via__filtros {
  position: sticky; top: 0; z-index: 30;
  display: flex; flex-wrap: wrap; align-items: center; gap: .6rem;
  background: var(--color-white); border: 1px solid var(--color-gray-border);
  border-radius: var(--radius-md); padding: .7rem .9rem; box-shadow: var(--shadow-card);
}
.via__filtros-limpiar { margin-left: auto; background: none; border: none; color: var(--color-teal-dark); font-weight: 700; font-size: .82rem; cursor: pointer; text-decoration: underline; padding: .3rem; }
.via__filtros-limpiar:hover { color: var(--color-danger); }

/* Multiselect con buscador */
.ms { position: relative; }
.ms__btn {
  display: inline-flex; align-items: center; gap: .35rem; border: 1px solid var(--color-gray-border);
  background: var(--color-gray-bg-alt); color: var(--color-navy); font: inherit; font-weight: 700;
  font-size: .82rem; padding: .5rem .9rem; border-radius: var(--radius-pill); cursor: pointer;
}
.ms__btn:hover { border-color: var(--color-teal); }
.ms__btn.activo { background: rgba(15, 157, 128, .14); border-color: var(--color-teal); color: var(--color-teal-dark); }
.ms__panel {
  position: absolute; top: calc(100% + 6px); left: 0; min-width: 260px; max-width: 320px;
  background: var(--color-white); border: 1px solid var(--color-gray-border); border-radius: var(--radius-sm);
  box-shadow: 0 10px 28px rgba(0, 0, 0, .14); padding: .6rem; z-index: 40; display: none;
}
.ms__panel.abierto { display: block; }
.ms__buscar { width: 100%; box-sizing: border-box; padding: .4rem .6rem; border: 1px solid var(--color-gray-border); border-radius: 8px; font: inherit; font-size: .82rem; margin-bottom: .5rem; }
.ms__buscar:focus { outline: 2px solid var(--color-teal); outline-offset: 1px; }
.ms__lista { max-height: 240px; overflow-y: auto; display: flex; flex-direction: column; gap: .1rem; }
.ms__opcion { display: flex; align-items: center; gap: .5rem; padding: .3rem .35rem; border-radius: 6px; font-size: .82rem; cursor: pointer; }
.ms__opcion:hover { background: var(--color-gray-bg-alt); }
.ms__opcion input { accent-color: var(--color-teal); }
.ms__vacio { color: var(--color-gray-text); font-size: .8rem; padding: .3rem; }
"""


LOGO_ALTURA_PX = 56


def _logo_html() -> str:
    if not LOGO_PATH.exists():
        return ""
    data_uri = "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    # El logo real es un membrete horizontal (2550x407 px, ratio ~6.3:1), no
    # un icono cuadrado -- el ancho se calcula desde la proporcion real del
    # archivo (nunca hardcodeado) para no achicarlo/distorsionarlo forzandolo
    # a un cuadrado, que es lo que lo volvia ilegible.
    with Image.open(LOGO_PATH) as im:
        ancho_px = round(LOGO_ALTURA_PX * im.width / im.height)
    return f'<img class="via__pin" src="{data_uri}" alt="Logo" width="{ancho_px}" height="{LOGO_ALTURA_PX}" />'


APP_JS = """
(function () {
  var D = window.__DATA__;
  var TODAS = D.filas;
  var MESES_JS = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  var MESES_CORTOS = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  var TEALES = ['#0f9d80', '#0b7a63', '#5bc9ae', '#17293b', '#3a4f63', '#7fd9c3', '#0a5c4a', '#a7e6d5', '#264257', '#0d8a70'];

  var filtros = { gerencia: new Set(), subgerencia: new Set(), sociedad: new Set(), aprobador: new Set(), nombre: new Set(), mes: new Set() };

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function mesDe(fIso) {
    var partes = fIso.split('-');
    return MESES_JS[parseInt(partes[1], 10)] + ' ' + partes[0];
  }

  function formatCLP(v) {
    return '$' + Math.round(v).toLocaleString('es-CL');
  }

  function formatCLPCorto(v) {
    var abs = Math.abs(v);
    if (abs >= 1e6) return '$' + (v / 1e6).toFixed(1).replace('.', ',') + 'M';
    if (abs >= 1e3) return '$' + Math.round(v / 1e3) + 'K';
    return formatCLP(v);
  }

  function formatFecha(fIso) {
    var p = fIso.split('-');
    return p[2] + '-' + p[1] + '-' + p[0];
  }

  // ---------- Filtrado ----------
  // "campoExcluido" deja afuera del filtrado esa dimension -- se usa para
  // calcular, para cada multiselect, que opciones siguen teniendo datos
  // segun los DEMAS filtros activos (filtros vinculados/en cascada, ej.
  // Gerencia -> Sub-gerencia), sin que un filtro se autoexcluya sus propias
  // opciones ya seleccionadas.
  function filasFiltradasExcepto(campoExcluido) {
    return TODAS.filter(function (r) {
      if (campoExcluido !== 'gerencia' && filtros.gerencia.size && !filtros.gerencia.has(r.g)) return false;
      if (campoExcluido !== 'subgerencia' && filtros.subgerencia.size && !filtros.subgerencia.has(r.sg)) return false;
      if (campoExcluido !== 'sociedad' && filtros.sociedad.size && !filtros.sociedad.has(r.s)) return false;
      if (campoExcluido !== 'aprobador' && filtros.aprobador.size && !filtros.aprobador.has(r.ap)) return false;
      if (campoExcluido !== 'nombre' && filtros.nombre.size && !filtros.nombre.has(r.n)) return false;
      if (campoExcluido !== 'mes' && filtros.mes.size && !filtros.mes.has(mesDe(r.f))) return false;
      return true;
    });
  }

  function filasFiltradas() {
    return filasFiltradasExcepto(null);
  }

  var EXTRACTORES_FILTRO = {
    gerencia: function (r) { return r.g; },
    subgerencia: function (r) { return r.sg; },
    sociedad: function (r) { return r.s; },
    aprobador: function (r) { return r.ap; },
    nombre: function (r) { return r.n; },
    mes: function (r) { return mesDe(r.f); },
  };

  function claveMes(label) {
    var partes = label.split(' ');
    var anio = partes[partes.length - 1];
    var idx = MESES_JS.indexOf(partes.slice(0, -1).join(' '));
    return anio + '-' + (idx < 10 ? '0' + idx : String(idx));
  }

  // "AAAA-MM" directo desde una fecha ISO (para agrupar por mes en Alertas,
  // distinto de claveMes() que parte de un label "Mes Año").
  function claveMesIso(fIso) {
    var p = fIso.split('-');
    return p[0] + '-' + p[1];
  }

  // Opciones vigentes de un filtro segun los DEMAS filtros activos (no segun
  // el propio, para no autoexcluirse su seleccion actual).
  function opcionesDisponibles(campo) {
    var filas = filasFiltradasExcepto(campo);
    var extraer = EXTRACTORES_FILTRO[campo];
    var vistos = {};
    filas.forEach(function (r) { vistos[extraer(r)] = true; });
    var lista = Object.keys(vistos);
    return campo === 'mes'
      ? lista.sort(function (a, b) { return claveMes(a) < claveMes(b) ? -1 : claveMes(a) > claveMes(b) ? 1 : 0; })
      : lista.sort();
  }

  function sumarPor(filas, claveFn) {
    var mapa = {};
    filas.forEach(function (r) { var k = claveFn(r); mapa[k] = (mapa[k] || 0) + r.v; });
    var entradas = Object.keys(mapa).map(function (k) { return [k, mapa[k]]; });
    entradas.sort(function (a, b) { return b[1] - a[1]; });
    return { labels: entradas.map(function (e) { return e[0]; }), valores: entradas.map(function (e) { return e[1]; }) };
  }

  // ---------- Alertas ----------
  // Toda la seccion "Alertas" (incluido el Ranking de Aprobadores) ignora el
  // filtro de Mes a proposito -- son una foto del ULTIMO mes disponible vs.
  // el promedio historico, asi que necesitan el historial completo de meses
  // para tener sentido (si dependiera de Mes, filtrar a un solo mes dejaria
  // "salto mensual" sin meses anteriores contra que comparar). Si respeta el
  // resto de los filtros (Gerencia, Sub-gerencia, Sociedad, Aprobador,
  // Nombre) -- ver la llamada a renderAlertas() en actualizar().
  var UMBRAL_PCT_PERSONA = 50;
  var UMBRAL_PCT_GERENCIA = 50;

  function calcularAlertas(filas) {
    if (!filas.length) return { ultimoLabel: null, saltoPersona: [], saltoGerencia: [] };

    var ultimaClave = filas.reduce(function (max, r) {
      var c = claveMesIso(r.f);
      return c > max ? c : max;
    }, '');
    var ultimoLabel = mesDe(filas.filter(function (r) { return claveMesIso(r.f) === ultimaClave; })[0].f);

    // 1) Colaboradores con salto mensual: monto del ultimo mes vs. el
    // promedio de SUS OTROS meses con viatico (no cuenta meses sin
    // actividad como $0, para no inflar el % de alguien que recien empieza
    // a viajar seguido).
    var porPersonaMes = {}, nombrePorId = {}, sociedadPorId = {};
    filas.forEach(function (r) {
      var clave = claveMesIso(r.f);
      if (!porPersonaMes[r.id]) porPersonaMes[r.id] = {};
      porPersonaMes[r.id][clave] = (porPersonaMes[r.id][clave] || 0) + r.v;
      nombrePorId[r.id] = r.n; sociedadPorId[r.id] = r.s;
    });
    var saltoPersona = [];
    Object.keys(porPersonaMes).forEach(function (id) {
      var meses = porPersonaMes[id];
      var montoUltimo = meses[ultimaClave] || 0;
      var anteriores = Object.keys(meses).filter(function (c) { return c !== ultimaClave; });
      if (!anteriores.length) return;
      var promedioAnterior = anteriores.reduce(function (s, c) { return s + meses[c]; }, 0) / anteriores.length;
      if (promedioAnterior <= 0) return;
      var pct = ((montoUltimo - promedioAnterior) / promedioAnterior) * 100;
      if (pct < UMBRAL_PCT_PERSONA) return;
      // Semaforo: 50%+ moderado (amarillo), 80%+ alto (rojo suave), 100%+
      // muy alto (rojo fuerte).
      var nivel = pct >= 100 ? 'muyalto' : pct >= 80 ? 'alto' : 'moderado';
      saltoPersona.push({ nivel: nivel, nombre: nombrePorId[id], sociedad: sociedadPorId[id], promedio_gasto: Math.round(promedioAnterior), monto_ultimo: Math.round(montoUltimo), aumento_pct: Math.round(pct) });
    });
    saltoPersona.sort(function (a, b) { return b.aumento_pct - a.aumento_pct; });

    // 2) Gerencias con salto mensual: mismo criterio que (1), agregado.
    var porGerenciaMes = {};
    filas.forEach(function (r) {
      var clave = claveMesIso(r.f);
      if (!porGerenciaMes[r.g]) porGerenciaMes[r.g] = {};
      porGerenciaMes[r.g][clave] = (porGerenciaMes[r.g][clave] || 0) + r.v;
    });
    var saltoGerencia = [];
    Object.keys(porGerenciaMes).forEach(function (g) {
      var meses = porGerenciaMes[g];
      var montoUltimo = meses[ultimaClave] || 0;
      var anteriores = Object.keys(meses).filter(function (c) { return c !== ultimaClave; });
      if (!anteriores.length) return;
      var promedioAnterior = anteriores.reduce(function (s, c) { return s + meses[c]; }, 0) / anteriores.length;
      if (promedioAnterior <= 0) return;
      var pct = ((montoUltimo - promedioAnterior) / promedioAnterior) * 100;
      if (pct >= UMBRAL_PCT_GERENCIA) {
        saltoGerencia.push({ gerencia: g, promedio_anterior: Math.round(promedioAnterior), monto_ultimo: Math.round(montoUltimo), aumento_pct: Math.round(pct) });
      }
    });
    saltoGerencia.sort(function (a, b) { return b.aumento_pct - a.aumento_pct; });

    return { ultimoLabel: ultimoLabel, saltoPersona: saltoPersona, saltoGerencia: saltoGerencia };
  }

  // Ranking de Aprobadores por monto: recibe el mismo conjunto de filas que
  // el resto de "Alertas" (todos los filtros salvo Mes, ver renderAlertas()
  // en actualizar()). No se agrupa por Gerencia: es el monto de cada
  // aprobador sobre el total de lo que este filtrado en cada momento (si el
  // usuario filtra por Gerencia arriba, el ranking queda acotado a esa
  // Gerencia sola).
  function calcularConcentracionAprobador(filas) {
    if (!filas.length) return [];
    var porAprobador = {}, totalGeneral = 0;
    filas.forEach(function (r) {
      totalGeneral += r.v;
      if (!porAprobador[r.ap]) porAprobador[r.ap] = { total: 0, count: 0 };
      porAprobador[r.ap].total += r.v;
      porAprobador[r.ap].count++;
    });
    if (totalGeneral <= 0) return [];
    var resultado = Object.keys(porAprobador).map(function (ap) {
      var datos = porAprobador[ap];
      return { aprobador: ap, pct: Math.round((datos.total / totalGeneral) * 100), monto: Math.round(datos.total), n_viaticos: datos.count };
    });
    resultado.sort(function (a, b) { return b.monto - a.monto; });
    return resultado;
  }

  // ---------- Agregacion ----------
  function recalcular(filas) {
    var total = filas.reduce(function (s, r) { return s + r.v; }, 0);
    var idsUnicos = {};
    filas.forEach(function (r) { idsUnicos[r.id] = true; });
    var colaboradores = Object.keys(idsUnicos).length;
    var gerenciasUnicas = {};
    filas.forEach(function (r) { gerenciasUnicas[r.g] = true; });
    var sociedadesUnicas = {};
    filas.forEach(function (r) { sociedadesUnicas[r.s] = true; });

    var kpis = {
      total: total,
      n_viaticos: filas.length,
      colaboradores: colaboradores,
      ticket_promedio: filas.length ? total / filas.length : 0,
      gerencias: Object.keys(gerenciasUnicas).length,
      sociedades: Object.keys(sociedadesUnicas).length,
    };

    // Evolucion mensual, ordenada cronologicamente (no alfabeticamente)
    var porMes = {};
    filas.forEach(function (r) {
      var partes = r.f.split('-');
      var clave = partes[0] + '-' + partes[1];
      porMes[clave] = (porMes[clave] || 0) + r.v;
    });
    var clavesOrdenadas = Object.keys(porMes).sort();
    var evolucion = {
      labels: clavesOrdenadas.map(function (c) {
        var p = c.split('-');
        return MESES_CORTOS[parseInt(p[1], 10)] + ' ' + p[0];
      }),
      valores: clavesOrdenadas.map(function (c) { return porMes[c]; }),
    };

    var gastoGerencia = sumarPor(filas, function (r) { return r.g; });
    // El nombre de Sub-gerencia solo se prefija con la Gerencia cuando es
    // ambiguo -- el mismo texto de Sub-gerencia aparece bajo mas de una
    // Gerencia (ej. "(Sin subgerencia)"), o coincide textualmente con el
    // nombre de OTRA Gerencia real (dato de origen: hay filas de "Gerencia
    // de Operaciones" con la columna Sub-gerencia cargada literalmente como
    // "Gerencia de Perdidas" en el Excel -- sin este segundo chequeo, esas
    // barras se verian identicas a las de la Gerencia de Perdidas real).
    var gerenciasVistas = {};
    filas.forEach(function (r) { gerenciasVistas[r.g] = true; });
    var gerenciasPorSub = {};
    filas.forEach(function (r) {
      if (!gerenciasPorSub[r.sg]) gerenciasPorSub[r.sg] = {};
      gerenciasPorSub[r.sg][r.g] = true;
    });
    var gastoSubgerencia = sumarPor(filas, function (r) {
      var ambiguo = Object.keys(gerenciasPorSub[r.sg]).length > 1
        || (r.sg !== r.g && gerenciasVistas[r.sg]);
      return ambiguo ? r.g + ' \\u00b7 ' + r.sg : r.sg;
    });

    // Ranking de colaboradores: se agrupa por id (no por nombre, ver
    // _mapa_ids en Python) para no fusionar por error dos personas
    // distintas con el mismo nombre.
    var porPersona = {};
    filas.forEach(function (r) {
      if (!porPersona[r.id]) porPersona[r.id] = { nombre: r.n, gerencia: r.g, subgerencia: r.sg, n_viaticos: 0, total: 0 };
      var P = porPersona[r.id];
      P.n_viaticos++;
      P.total += r.v;
      // Si la persona aparece bajo mas de una Gerencia/Subgerencia en el
      // periodo filtrado, se queda con la del ultimo registro (por fecha).
      P.gerencia = r.g;
      P.subgerencia = r.sg;
    });
    var ranking = Object.keys(porPersona).map(function (id) { return porPersona[id]; })
      .sort(function (a, b) { return b.total - a.total; });

    var detalle = filas.map(function (r) {
      return { numero: r.no, documento_sap: r.sap, fecha: formatFecha(r.f), _fecha_iso: r.f, nombre: r.n, gerencia: r.g, subgerencia: r.sg, aprobador: r.ap, sociedad: r.s, mes: mesDe(r.f), cuenta: r.ct, importe: r.v };
    }).sort(function (a, b) { return b._fecha_iso < a._fecha_iso ? -1 : 1; });

    return { kpis: kpis, evolucion: evolucion, gastoGerencia: gastoGerencia, gastoSubgerencia: gastoSubgerencia, ranking: ranking, detalle: detalle };
  }

  // ---------- Render: Resumen / KPIs ----------
  function kpi(label, value, cls) {
    return '<div class="kpi"><div class="label">' + label + '</div><div class="value ' + (cls || '') + '">' + value + '</div></div>';
  }

  function renderResumen(K) {
    document.getElementById('kpis').innerHTML = [
      kpi('Total gastado', formatCLP(K.total), 'acento'),
      kpi('N. de viaticos', K.n_viaticos.toLocaleString('es-CL')),
      kpi('Colaboradores con viatico', K.colaboradores.toLocaleString('es-CL')),
      kpi('Ticket promedio', formatCLP(K.ticket_promedio)),
      kpi('Gerencias', K.gerencias),
      kpi('Sociedades', K.sociedades),
    ].join('');
  }

  // ---------- Render: graficos ----------
  var chartEvolucion = new Chart(document.getElementById('chart-evolucion'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Gasto', data: [], backgroundColor: '#0f9d80', borderRadius: 6, maxBarThickness: 60 }] },
    plugins: [ChartDataLabels],
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, ticks: { callback: function (v) { return formatCLPCorto(v); } } } },
      plugins: {
        legend: { display: false },
        datalabels: { anchor: 'end', align: 'top', color: '#17293b', font: { weight: '700', size: 11 }, formatter: function (v) { return formatCLPCorto(v); } },
      },
    },
  });

  function chartBarraHorizontal(canvasId) {
    return new Chart(document.getElementById(canvasId), {
      type: 'bar',
      data: { labels: [], datasets: [{ label: 'Gasto', data: [], backgroundColor: '#0f9d80', borderRadius: 6 }] },
      plugins: [ChartDataLabels],
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: 'y',
        // grace: deja espacio extra al final del eje para que el valor mas
        // alto tambien quepa afuera de la barra, sin cortarse contra el
        // borde del grafico.
        scales: { x: { beginAtZero: true, grace: '12%', ticks: { callback: function (v) { return formatCLPCorto(v); } } } },
        plugins: {
          legend: { display: false },
          // Etiqueta afuera de la barra (a la derecha de su extremo) en vez
          // de centrada adentro -- con montos chicos la barra es mas angosta
          // que el propio texto y quedaba tapado/invisible.
          datalabels: { color: '#17293b', font: { weight: '700', size: 10 }, anchor: 'end', align: 'right', formatter: function (v) { return formatCLPCorto(v); } },
        },
      },
    });
  }

  var chartGerencia = chartBarraHorizontal('chart-gerencia');
  var chartSubgerencia = chartBarraHorizontal('chart-subgerencia');

  function actualizarGraficos(res) {
    chartEvolucion.data.labels = res.evolucion.labels;
    chartEvolucion.data.datasets[0].data = res.evolucion.valores;
    chartEvolucion.update();

    chartGerencia.data.labels = res.gastoGerencia.labels;
    chartGerencia.data.datasets[0].data = res.gastoGerencia.valores;
    document.getElementById('chart-gerencia-inner').style.height = Math.max(380, res.gastoGerencia.labels.length * 38) + 'px';
    chartGerencia.resize();
    chartGerencia.update();

    chartSubgerencia.data.labels = res.gastoSubgerencia.labels;
    chartSubgerencia.data.datasets[0].data = res.gastoSubgerencia.valores;
    document.getElementById('chart-subgerencia-inner').style.height = Math.max(380, res.gastoSubgerencia.labels.length * 38) + 'px';
    chartSubgerencia.resize();
    chartSubgerencia.update();
  }

  // ---------- Render: tablas ordenables ----------
  var RANGO_NIVEL = { muyalto: 0, alto: 1, moderado: 2 };
  var ETIQUETA_NIVEL = { muyalto: 'Muy alto', alto: 'Alto', moderado: 'Moderado' };

  function crearTabla(tablaId, formatos) {
    var tabla = document.getElementById(tablaId);
    var tbody = tabla.querySelector('tbody');
    var ths = Array.prototype.slice.call(tabla.querySelectorAll('th'));
    var estado = { key: null, asc: false };
    var filasActuales = [];

    function ordenarSiCorresponde() {
      if (!estado.key) return;
      var th = ths.filter(function (t) { return t.dataset.key === estado.key; })[0];
      var tipo = th ? th.dataset.tipo : 'str';
      filasActuales.sort(function (a, b) {
        var va = a[estado.key], vb = b[estado.key];
        if (tipo === 'num') { va = Number(va); vb = Number(vb); }
        if (tipo === 'nivel') { va = RANGO_NIVEL[va]; vb = RANGO_NIVEL[vb]; }
        if (va < vb) return estado.asc ? -1 : 1;
        if (va > vb) return estado.asc ? 1 : -1;
        return 0;
      });
    }

    function render() {
      tbody.innerHTML = filasActuales.map(function (f) {
        var filaCls = f.nivel ? ' class="row-nivel--' + f.nivel + '"' : '';
        return '<tr' + filaCls + '>' + ths.map(function (th) {
          var key = th.dataset.key;
          var tipo = th.dataset.tipo;
          var val = f[key];
          if (tipo === 'nivel') {
            return '<td><span class="badge-nivel badge-nivel--' + val + '">' + (ETIQUETA_NIVEL[val] || val) + '</span></td>';
          }
          if (formatos && formatos[key]) val = formatos[key](val);
          return '<td>' + escapeHtml(val) + '</td>';
        }).join('') + '</tr>';
      }).join('');
      if (!filasActuales.length) {
        tbody.innerHTML = '<tr><td colspan="' + ths.length + '" class="ms__vacio">Sin datos para los filtros seleccionados</td></tr>';
      }
    }

    ths.forEach(function (th) {
      th.addEventListener('click', function () {
        var key = th.dataset.key;
        estado.asc = estado.key === key ? !estado.asc : false;
        estado.key = key;
        ths.forEach(function (t) { t.classList.remove('sorted', 'asc'); });
        th.classList.add('sorted');
        if (estado.asc) th.classList.add('asc');
        ordenarSiCorresponde();
        render();
      });
    });

    return {
      actualizar: function (nuevasFilas) {
        filasActuales = nuevasFilas;
        ordenarSiCorresponde();
        render();
      },
    };
  }

  var tablaRanking = crearTabla('tabla-ranking', { total: formatCLP });
  var tablaDetalle = crearTabla('tabla-detalle', { importe: formatCLP });

  function formatPct(v) { return (v >= 0 ? '+' : '') + v + '%'; }
  function formatPctPlano(v) { return v + '%'; }

  var tablaAlertaPersona = crearTabla('tabla-alerta-persona', { promedio_gasto: formatCLP, monto_ultimo: formatCLP, aumento_pct: formatPct });
  var tablaAlertaGerencia = crearTabla('tabla-alerta-gerencia', { promedio_anterior: formatCLP, monto_ultimo: formatCLP, aumento_pct: formatPct });
  var tablaAlertaAprobador = crearTabla('tabla-alerta-aprobador', { pct: formatPctPlano, monto: formatCLP });

  function renderAlertas(filas) {
    var A = calcularAlertas(filas);
    // El ranking de Aprobadores no cuenta como "alerta" (ya no es un umbral,
    // es una lista completa) -- se muestra en la misma seccion pero afuera
    // del conteo/banner de arriba.
    var total = A.saltoPersona.length + A.saltoGerencia.length;
    document.getElementById('alerta-resumen-num').textContent = total;
    document.getElementById('alerta-resumen-texto').textContent = A.ultimoLabel
      ? (total === 1 ? '1 alerta detectada' : total + ' alertas detectadas') + ' sobre la vista filtrada actual' + (A.ultimoLabel ? ' (ultimo mes disponible: ' + A.ultimoLabel + ')' : '') + '.'
      : 'Sin datos suficientes para evaluar alertas con los filtros actuales.';
    tablaAlertaPersona.actualizar(A.saltoPersona);
    tablaAlertaGerencia.actualizar(A.saltoGerencia);
    tablaAlertaAprobador.actualizar(calcularConcentracionAprobador(filas));
  }

  // ---------- Multiselect con buscador ----------
  function crearMultiSelect(contenedor, etiqueta, opciones, alCambiar) {
    var seleccion = new Set();
    var abierto = false;

    var wrap = document.createElement('div');
    wrap.className = 'ms';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ms__btn';
    var panel = document.createElement('div');
    panel.className = 'ms__panel';
    var buscar = document.createElement('input');
    buscar.type = 'text';
    buscar.className = 'ms__buscar';
    buscar.placeholder = 'Buscar ' + etiqueta.toLowerCase() + '...';
    var lista = document.createElement('div');
    lista.className = 'ms__lista';
    panel.appendChild(buscar);
    panel.appendChild(lista);
    wrap.appendChild(btn);
    wrap.appendChild(panel);

    function actualizarBoton() {
      btn.textContent = etiqueta + (seleccion.size ? ' (' + seleccion.size + ')' : '');
      btn.classList.toggle('activo', seleccion.size > 0);
    }

    function pintarLista(filtroTexto) {
      var texto = (filtroTexto || '').toLowerCase();
      var filtradas = opciones.filter(function (o) { return o.toLowerCase().indexOf(texto) !== -1; });
      if (!filtradas.length) { lista.innerHTML = '<div class="ms__vacio">Sin resultados</div>'; return; }
      lista.innerHTML = filtradas.map(function (o) {
        var marcado = seleccion.has(o) ? ' checked' : '';
        return '<label class="ms__opcion"><input type="checkbox" value="' + escapeHtml(o) + '"' + marcado + '/><span>' + escapeHtml(o) + '</span></label>';
      }).join('');
    }

    lista.addEventListener('change', function (e) {
      var input = e.target;
      if (input.tagName !== 'INPUT') return;
      if (input.checked) seleccion.add(input.value); else seleccion.delete(input.value);
      actualizarBoton();
      alCambiar(seleccion);
    });
    buscar.addEventListener('input', function () { pintarLista(buscar.value); });
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      abierto = !abierto;
      panel.classList.toggle('abierto', abierto);
      if (abierto) { buscar.value = ''; pintarLista(''); buscar.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (!wrap.contains(e.target)) { abierto = false; panel.classList.remove('abierto'); }
    });

    actualizarBoton();
    pintarLista('');
    contenedor.appendChild(wrap);

    return {
      limpiar: function () { seleccion.clear(); actualizarBoton(); pintarLista(buscar.value); },
      // Refresca el universo de opciones (filtros en cascada). Si la nueva
      // lista deja afuera algo que estaba seleccionado (ya no tiene datos
      // segun los demas filtros activos), se quita solo -- mismo Set que
      // filtros[campo] (se pasa por referencia), asi que el filtro real
      // queda corregido sin esperar otra interaccion del usuario.
      actualizarOpciones: function (nuevas) {
        opciones = nuevas;
        var huboPoda = false;
        seleccion.forEach(function (v) {
          if (nuevas.indexOf(v) === -1) { seleccion.delete(v); huboPoda = true; }
        });
        actualizarBoton();
        if (abierto) pintarLista(buscar.value);
        return huboPoda;
      },
    };
  }

  var msGerencia = crearMultiSelect(document.getElementById('filtro-gerencia'), 'Gerencia', D.opciones.gerencias, function (sel) { filtros.gerencia = sel; actualizar(); });
  var msSubgerencia = crearMultiSelect(document.getElementById('filtro-subgerencia'), 'Sub-gerencia', D.opciones.subgerencias, function (sel) { filtros.subgerencia = sel; actualizar(); });
  var msSociedad = crearMultiSelect(document.getElementById('filtro-sociedad'), 'Sociedad', D.opciones.sociedades, function (sel) { filtros.sociedad = sel; actualizar(); });
  var msAprobador = crearMultiSelect(document.getElementById('filtro-aprobador'), 'Aprobador', D.opciones.aprobadores, function (sel) { filtros.aprobador = sel; actualizar(); });
  var msNombre = crearMultiSelect(document.getElementById('filtro-nombre'), 'Nombre', D.opciones.nombres, function (sel) { filtros.nombre = sel; actualizar(); });
  var msMes = crearMultiSelect(document.getElementById('filtro-mes'), 'Mes', D.opciones.meses, function (sel) { filtros.mes = sel; actualizar(); });

  // Filtros vinculados: las opciones de cada multiselect se recalculan segun
  // los DEMAS filtros activos (ej. filtrar Gerencia acota Sub-gerencia, y
  // tambien al reves). Si podar una seleccion invalida cambia el resultado,
  // se vuelve a correr una vez mas para que todo (KPIs, graficos, tablas y
  // el resto de las listas) quede consistente con la poda.
  function refrescarOpciones() {
    var cambio = false;
    if (msGerencia.actualizarOpciones(opcionesDisponibles('gerencia'))) cambio = true;
    if (msSubgerencia.actualizarOpciones(opcionesDisponibles('subgerencia'))) cambio = true;
    if (msSociedad.actualizarOpciones(opcionesDisponibles('sociedad'))) cambio = true;
    if (msAprobador.actualizarOpciones(opcionesDisponibles('aprobador'))) cambio = true;
    if (msNombre.actualizarOpciones(opcionesDisponibles('nombre'))) cambio = true;
    if (msMes.actualizarOpciones(opcionesDisponibles('mes'))) cambio = true;
    return cambio;
  }

  function actualizar() {
    if (refrescarOpciones()) refrescarOpciones();
    var filas = filasFiltradas();
    var res = recalcular(filas);
    renderResumen(res.kpis);
    actualizarGraficos(res);
    tablaRanking.actualizar(res.ranking);
    tablaDetalle.actualizar(res.detalle);
    // Alertas ignora el filtro de Mes a proposito: son una foto del ultimo
    // mes vs. el promedio historico, asi que necesitan el historial completo
    // de meses (respetan los demas filtros igual que el resto del reporte).
    renderAlertas(filasFiltradasExcepto('mes'));
  }

  document.getElementById('btn-limpiar-filtros').addEventListener('click', function () {
    filtros = { gerencia: new Set(), subgerencia: new Set(), sociedad: new Set(), aprobador: new Set(), nombre: new Set(), mes: new Set() };
    msGerencia.limpiar(); msSubgerencia.limpiar(); msSociedad.limpiar(); msAprobador.limpiar(); msNombre.limpiar(); msMes.limpiar();
    actualizar();
  });

  actualizar();
})();
"""


def generar_reporte_html(ruta_excel: Path, destino: Path | None = None) -> Path:
    df = cargar_datos(ruta_excel)
    datos = construir_datos_reporte(df)
    periodo = _periodo(df)

    if destino is None:
        carpeta = PROJECT_ROOT / "data" / "reportes"
        carpeta.mkdir(parents=True, exist_ok=True)
        ts = pd.Timestamp.now().strftime("%Y-%m-%d_%H%M%S")
        destino = carpeta / f"{_nombre_archivo(df)}_{ts}.html"

    chartjs = CHARTJS_PATH.read_text(encoding="utf-8")
    chartjs_datalabels = CHARTJS_DATALABELS_PATH.read_text(encoding="utf-8")

    html = HTML_TEMPLATE.format(
        periodo=periodo,
        logo_html=_logo_html(),
        fecha_min=pd.Timestamp(datos["fecha_min"]).strftime("%d-%m-%Y"),
        fecha_max=pd.Timestamp(datos["fecha_max"]).strftime("%d-%m-%Y"),
        generado_el=pd.Timestamp.now().strftime("%d-%m-%Y %H:%M"),
        generado_por=GENERADO_POR,
        estilos=ESTILOS,
        chartjs=chartjs,
        chartjs_datalabels=chartjs_datalabels,
        datos_json=json.dumps(datos, ensure_ascii=False),
        app_js=APP_JS,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return destino


def main(archivo=None, salida=None):
    ruta = Path(archivo) if archivo else NORMALIZADO
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontro el Excel normalizado: {ruta}\n"
            "Corre primero: venv\\Scripts\\python.exe Viaticos\\normalizar_viaticos.py \"ruta\\al_Informe_VI.xlsx\""
        )
    destino = Path(salida) if salida else None
    resultado = generar_reporte_html(ruta, destino)
    print(f"Reporte generado: {resultado}")


if __name__ == "__main__":
    arg_archivo = sys.argv[1] if len(sys.argv) > 1 else None
    arg_salida = sys.argv[2] if len(sys.argv) > 2 else None
    main(arg_archivo, arg_salida)
