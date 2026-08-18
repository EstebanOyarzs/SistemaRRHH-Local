"""
================================================================================
GENERADOR DE REPORTE HTML DE ASISTENCIA (GeoVictoria)
================================================================================
Lee el Excel bruto "Gestion de Asistencia" que exporta GeoVictoria (control de
ingreso/salida) y genera un reporte HTML autocontenido (datos + Chart.js
embebidos, sin necesitar servidor ni conexion a internet para abrirlo),
siguiendo el mismo patron visual del dashboard de Sobretiempo pero en tonos
azules.

USO:
    venv\\Scripts\\python.exe Geovictoria\\generar_reporte_asistencia.py "ruta\\archivo.xlsx"
    venv\\Scripts\\python.exe Geovictoria\\generar_reporte_asistencia.py "ruta\\archivo.xlsx" "ruta\\salida.html"

Si no se pasa archivo, usa el Excel de ejemplo en "Archivos ejemplo/".
================================================================================
"""

import base64
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
EJEMPLO = (
    PROJECT_ROOT
    / "Archivos ejemplo"
    / "GestióndeAsistencia202608181133_fd93e69e-7a4f-4a3f-aa6f-d087c0dbcfcf.xlsx"
)
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

COLUMNAS = [
    "Apellidos", "Nombre", "Identificador", "Grupo", "Fecha", "Permiso",
    "Turno", "Entro1", "Tipo1", "Atraso", "Just1", "Salio1", "Tipo2",
    "Adelanto", "Just2", "Entro2", "Tipo3", "Atraso2", "Just3", "Salio2",
    "Tipo4", "Adelanto2", "Just4", "HEA", "HEC", "HNT", "HT", "Cargo",
]


def _to_min(td) -> float:
    """Convierte un timedelta (o NaN) de pandas a minutos (float)."""
    if pd.isna(td):
        return 0.0
    return td.total_seconds() / 60.0


def _parse_fecha(texto: str) -> date:
    # Formato "Vie 14-08-2026" -> nos quedamos con la parte de la fecha
    partes = texto.split(" ")
    d, m, y = partes[1].split("-")
    return date(int(y), int(m), int(d))


def _normalizar_permiso(valor) -> object:
    """Limpia valores compuestos que llegan sucios desde GeoVictoria, ej.
    "Vacaciones; Vacaciones" (el mismo permiso repetido separado por ";")."""
    if pd.isna(valor):
        return valor
    partes = [p.strip() for p in str(valor).split(";") if p.strip()]
    vistas = []
    for p in partes:
        if p not in vistas:
            vistas.append(p)
    return "; ".join(vistas) if vistas else valor


def cargar_datos(ruta_excel: Path) -> pd.DataFrame:
    df = pd.read_excel(ruta_excel, sheet_name=0, skiprows=1, names=COLUMNAS, engine="openpyxl")
    df = df.dropna(how="all")
    df["Fecha_dt"] = df["Fecha"].apply(_parse_fecha)
    df["Permiso"] = df["Permiso"].apply(_normalizar_permiso)
    df["Just1"] = df["Just1"].apply(lambda v: v.strip() if isinstance(v, str) else v)
    for col in ("Atraso", "Atraso2", "Adelanto", "Adelanto2", "HEA", "HEC", "HNT", "HT"):
        df[col + "_min"] = df[col].apply(_to_min)
    df["Marco_Entrada"] = df["Entro1"].notna()
    # No se rastrea colacion (Salio1/Entro2 son el par de salida/vuelta de
    # almuerzo): "marco salida" = tiene CUALQUIER salida del dia, sea la de
    # colacion (Salio1, cuando no vuelve a marcar Entro2/Salio2) o la final
    # (Salio2). Solo interesa si cerro el dia, no el detalle de colacion.
    df["Marco_Salida"] = df["Salio1"].notna() | df["Salio2"].notna()
    df["Es_Descanso"] = df["Turno"] == "Descanso"
    df["Tiene_Permiso"] = df["Permiso"] != "Ninguno"
    # Ojo: "Permiso" puede ser un beneficio permanente (ej. "Amamantamiento")
    # que GeoVictoria marca en TODOS los dias del mes de la persona, no solo
    # el/los dia(s) que realmente falto. Por eso "falta explicada por permiso"
    # exige ademas que no haya marcaje ese dia puntual — si marco entrada,
    # trabajo, sin importar que el permiso este activo.
    df["Falta_Con_Permiso"] = (~df["Marco_Entrada"]) & df["Tiene_Permiso"] & (~df["Es_Descanso"])
    # "Atraso" ya viene en 0 desde GeoVictoria cuando el atraso tiene
    # justificacion escrita (Just1) — comprobado contra el Excel real: NINGUNA
    # fila con Just1 informado tiene Atraso > 0, aunque la hora de entrada sea
    # objetivamente posterior al inicio de turno. Es decir, "Atraso" > 0 ya
    # excluye por diseño las llegadas tarde perdonadas; Just1 se guarda aparte
    # solo como metrica informativa de "llegadas tarde justificadas".
    df["Llegada_Justificada"] = df["Just1"].notna()
    df["Nombre_Completo"] = (df["Nombre"].fillna("") + " " + df["Apellidos"].fillna("")).str.strip()
    return df


def construir_datos_reporte(df: pd.DataFrame) -> dict:
    # "Corte": ultimo dia con marcajes reales -> evita contar como ausencia
    # dias futuros del mes que aun no ocurren.
    con_marcaje = df[df["Marco_Entrada"]]
    fecha_corte = con_marcaje["Fecha_dt"].max() if not con_marcaje.empty else df["Fecha_dt"].max()

    vigente = df[df["Fecha_dt"] <= fecha_corte].copy()

    # Todos los KPIs/graficos/tablas se recalculan en el navegador (ver
    # APP_JS) para poder responder a los filtros (Unidad, Nombre, Mes, Dia)
    # sin volver a generar el reporte. Aca solo se exporta el detalle
    # fila-por-fila (una fila = una persona en un dia) ya acotado a la fecha
    # de corte, con nombres de campo cortos para no inflar el HTML.
    filas = [
        {
            "id": r["Identificador"],
            "n": r["Nombre_Completo"],
            "g": r["Grupo"],
            "f": r["Fecha_dt"].isoformat(),
            "d": bool(r["Es_Descanso"]),
            "p": r["Permiso"],
            "fcp": bool(r["Falta_Con_Permiso"]),
            "me": bool(r["Marco_Entrada"]),
            "ms": bool(r["Marco_Salida"]),
            "am": round(float(r["Atraso_min"]), 1),
            "lj": bool(r["Llegada_Justificada"]),
            "ht": round(float(r["HT_min"]), 1),
        }
        for _, r in vigente.iterrows()
    ]

    unidades = sorted(vigente["Grupo"].dropna().unique().tolist())
    nombres = sorted(vigente["Nombre_Completo"].dropna().unique().tolist())
    meses_pares = sorted({(f.year, f.month) for f in vigente["Fecha_dt"]})
    meses = [f"{MESES[m]} {y}" for (y, m) in meses_pares]
    dias = sorted({f.day for f in vigente["Fecha_dt"]})
    dias_fmt = [f"{d:02d}" for d in dias]

    return {
        "fecha_corte": fecha_corte.strftime("%d-%m-%Y"),
        "fecha_corte_iso": fecha_corte.isoformat(),
        "filas": filas,
        "opciones": {
            "unidades": unidades,
            "nombres": nombres,
            "meses": meses,
            "dias": dias_fmt,
        },
    }


def _mes_periodo(df: pd.DataFrame) -> str:
    f = df["Fecha_dt"].max()
    return f"{MESES[f.month]} {f.year}"


HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Dashboard de Asistencia - {periodo}</title>
<style>
{estilos}
</style>
</head>
<body>
<div class="asis">
  <header class="asis__header">
    <div class="asis__title">
      {pin_svg}
      <div>
        <h1>Dashboard de Asistencia</h1>
        <p class="asis__subtitle">Control de ingreso y salida - {periodo}</p>
      </div>
    </div>
    <div class="asis__meta">
      <span>Datos al {fecha_corte}</span>
      <span>Generado el {generado_el} por {generado_por}</span>
    </div>
  </header>

  <div class="asis__filtros" id="filtros">
    <div class="asis__filtros-grupo" id="filtro-unidad"></div>
    <div class="asis__filtros-grupo" id="filtro-nombre"></div>
    <div class="asis__filtros-grupo" id="filtro-mes"></div>
    <div class="asis__filtros-grupo" id="filtro-dia"></div>
    <button class="asis__filtros-limpiar" id="btn-limpiar-filtros" type="button">Limpiar filtros</button>
  </div>

  <section>
    <h2>Resumen</h2>
    <div class="card">
      <p class="asis__saldo-subtitulo">Cumplimiento de asistencia sobre los dias laborables sin permiso, a la fecha de corte</p>
      <div class="asis__saldo-barra">
        <div class="asis__saldo-barra-asistencia" id="barra-asistencia"><span id="barra-asistencia-txt"></span></div>
        <div class="asis__saldo-barra-ausencia" id="barra-ausencia"><span id="barra-ausencia-txt"></span></div>
      </div>
      <div class="kpis" id="kpis"></div>
    </div>
  </section>

  <section>
    <h2>Evolucion diaria</h2>
    <div class="card">
      <div class="asis__chart"><canvas id="chart-evolucion"></canvas></div>
    </div>
  </section>

  <section>
    <h2>Atrasos y permisos</h2>
    <div class="asis__panel-grid">
      <div class="card">
        <h3>Atrasos por area</h3>
        <div class="asis__chart-scroll asis__chart-scroll--rows10">
          <div class="asis__chart-inner" id="chart-atrasos-area-inner"><canvas id="chart-atrasos-area"></canvas></div>
        </div>
      </div>
      <div class="card">
        <h3>Uso de permisos por tipo</h3>
        <div class="asis__chart asis__chart--donut"><canvas id="chart-permisos"></canvas></div>
      </div>
    </div>
  </section>

  <section>
    <h2>Detalle por area</h2>
    <div class="card asis__table-card">
      <div class="asis__table-wrap asis__table-wrap--scroll asis__table-wrap--rows10">
        <table id="tabla-area">
          <thead><tr>
            <th data-key="grupo" data-tipo="str">Area</th>
            <th data-key="dotacion" data-tipo="num">Dotacion</th>
            <th data-key="pct_asistencia" data-tipo="num">% Asistencia</th>
            <th data-key="atrasos" data-tipo="num">Atrasos</th>
            <th data-key="min_atraso" data-tipo="num">Min. atraso</th>
            <th data-key="ausencias" data-tipo="num">Ausencias</th>
            <th data-key="horas_trabajadas" data-tipo="num">Horas trabajadas</th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </section>

  <section>
    <h2>Alertas de asistencia</h2>
    <div class="card asis__table-card">
      <div class="alerta-resumen" id="alerta-resumen">
        <span class="alerta-resumen__num" id="alerta-resumen-num">0 de 0</span>
        <span class="alerta-resumen__texto" id="alerta-resumen-texto"></span>
      </div>
      <p class="asis__saldo-subtitulo"><span class="badge-nivel badge-nivel--critico">Critico</span> 8 o mas atrasos no justificados, 3 o mas ausencias injustificadas, o 4 o mas dias sin marcaje de salida. <span class="badge-nivel badge-nivel--advertencia">Advertencia</span> 4 o mas atrasos, 2 o mas ausencias, o 2 o mas dias sin marcaje de salida. <span class="badge-nivel badge-nivel--leve">Leve</span> al menos un atraso, ausencia o dia sin marcaje de salida, sin llegar a Advertencia.</p>
      <div class="asis__table-wrap asis__table-wrap--scroll asis__table-wrap--rows15">
        <table id="tabla-alertas">
          <thead><tr>
            <th data-key="nivel" data-tipo="nivel">Nivel</th>
            <th data-key="nombre" data-tipo="str">Nombre</th>
            <th data-key="grupo" data-tipo="str">Area</th>
            <th data-key="motivo" data-tipo="str">Motivo</th>
            <th data-key="atrasos" data-tipo="num">Atrasos</th>
            <th data-key="min_atraso" data-tipo="num">Min. atraso</th>
            <th data-key="ausencias" data-tipo="num">Ausencias</th>
            <th data-key="incompleto" data-tipo="num">Sin marcaje salida</th>
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
  /* Paleta GeoVictoria (geovictoria.com/es-cl) */
  --color-blue: #00aff2;
  --color-blue-dark: #0093cc;
  --color-blue-darker: #006b94;
  --color-amber: #ffbb00;
  --color-amber-dark: #e5a700;
  --color-navy: #171717;
  --color-navy-light: #3a3a3a;
  --color-gray-bg: #f4f8fb;
  --color-gray-bg-alt: #eaf6fd;
  --color-gray-border: #dde5eb;
  --color-gray-text: #646464;
  --color-white: #ffffff;
  --color-success: #0aa06e;
  --color-danger: #e2483a;
  --color-warning: var(--color-amber-dark);
  --font-family: "Nunito", "Segoe UI", sans-serif;
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-pill: 32px;
  --shadow-card: 0 4px 14px rgba(0, 107, 148, 0.1);
}
* { box-sizing: border-box; }
body { margin: 0; font-family: var(--font-family); background: var(--color-gray-bg); color: var(--color-navy); }
h1, h2, h3 { font-weight: 800; margin: 0 0 .5rem; }
.asis { display: flex; flex-direction: column; gap: 2rem; padding: 1.5rem 2rem 3rem; max-width: 1400px; margin: 0 auto; }
.asis__header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
  padding: 1.5rem 1.75rem; margin: -0.5rem -0.5rem 0; border-radius: var(--radius-md);
  background:
    radial-gradient(110% 140% at 0% -10%, rgba(0, 175, 242, 0.16), rgba(255, 255, 255, 0) 60%),
    radial-gradient(90% 140% at 100% -10%, rgba(255, 187, 0, 0.16), rgba(255, 255, 255, 0) 55%),
    var(--color-white);
  box-shadow: var(--shadow-card);
}
.asis__title { display: flex; align-items: center; gap: .6rem; }
.asis__pin { flex: 0 0 auto; object-fit: contain; }
.asis__subtitle { color: var(--color-gray-text); margin: 0; font-weight: 600; }
.asis__meta { display: flex; flex-direction: column; gap: .2rem; font-size: .82rem; color: var(--color-gray-text); text-align: right; }
.asis section h2 { border-left: 8px solid var(--color-blue); border-radius: 3px; padding-left: .6rem; margin-bottom: 1rem; }
.card { background: var(--color-white); border-radius: var(--radius-md); box-shadow: var(--shadow-card); padding: 1.25rem 1.5rem; border: 1px solid var(--color-gray-border); }
.asis__saldo-subtitulo { margin: 0 0 .9rem; font-size: .82rem; color: var(--color-gray-text); }
.asis__saldo-barra { display: flex; width: 100%; height: 36px; background: var(--color-gray-bg-alt); border-radius: var(--radius-pill); overflow: hidden; border: 1px solid var(--color-gray-border); }
.asis__saldo-barra-asistencia, .asis__saldo-barra-ausencia { display: flex; align-items: center; justify-content: center; height: 100%; overflow: hidden; white-space: nowrap; transition: width .3s ease; }
.asis__saldo-barra-asistencia span, .asis__saldo-barra-ausencia span { font-size: .78rem; font-weight: 700; color: var(--color-white); }
.asis__saldo-barra-asistencia { background: linear-gradient(90deg, var(--color-blue-dark), var(--color-blue)); }
.asis__saldo-barra-ausencia { background: var(--color-danger); }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin-top: 1.25rem; }
.kpi { background: var(--color-gray-bg-alt); border-radius: var(--radius-sm); padding: .9rem 1rem; display: flex; flex-direction: column; }
.kpi .label { font-size: .72rem; line-height: 1.35; color: var(--color-gray-text); font-weight: 700; text-transform: uppercase; letter-spacing: .03em; margin-bottom: .4rem; min-height: 1.95em; display: flex; align-items: flex-end; }
.kpi .value { font-size: 1.5rem; font-weight: 800; color: var(--color-navy); margin-top: auto; }
.kpi .value.danger { color: var(--color-danger); }
.kpi .value.success { color: var(--color-success); }
.asis__panel-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1rem; }
.asis__panel-grid .card h3 { font-size: .95rem; color: var(--color-navy); margin-bottom: .75rem; }
.asis__chart { height: 320px; position: relative; }
.asis__chart--donut { height: 260px; }
.asis__chart-scroll { overflow-y: auto; overflow-x: hidden; }
.asis__chart-scroll--rows10 { height: 380px; }
.asis__chart-inner { position: relative; width: 100%; height: 380px; }
.asis__table-wrap { overflow-x: auto; }
.asis__table-wrap--scroll { overflow-y: auto; }
.asis__table-wrap--scroll thead th { position: sticky; top: 0; background: var(--color-white); z-index: 1; }
.asis__table-wrap--rows10 { max-height: 380px; }
.asis__table-wrap--rows15 { max-height: 560px; }
.asis__table-card { margin-top: 0; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
thead th { text-align: left; color: var(--color-gray-text); font-weight: 700; padding: .5rem .6rem; border-bottom: 2px solid var(--color-gray-border); white-space: nowrap; cursor: pointer; user-select: none; }
thead th:hover { color: var(--color-blue-dark); }
thead th.sorted::after { content: " \\25BC"; font-size: .7rem; color: var(--color-blue); }
thead th.sorted.asc::after { content: " \\25B2"; }
tbody td { padding: .5rem .6rem; border-bottom: 1px solid var(--color-gray-border); white-space: nowrap; }
tbody tr:hover { background: var(--color-gray-bg-alt); }
.danger-text { color: var(--color-danger); font-weight: 700; }
.badge-nivel { display: inline-block; padding: .2rem .65rem; border-radius: var(--radius-pill); font-weight: 700; font-size: .78rem; white-space: nowrap; }
.badge-nivel--advertencia { background: rgba(255, 187, 0, .18); color: #8a6800; }
.badge-nivel--leve { background: rgba(0, 175, 242, .14); color: var(--color-blue-darker); }
.badge-nivel--critico { background: rgba(226, 72, 58, .16); color: var(--color-danger); }
.alerta-resumen {
  display: flex; align-items: center; gap: .9rem; flex-wrap: wrap;
  background: linear-gradient(90deg, rgba(226, 72, 58, .12), rgba(255, 187, 0, .12));
  border: 1px solid rgba(226, 72, 58, .3); border-radius: var(--radius-sm);
  padding: .9rem 1.1rem; margin-bottom: .9rem;
}
.alerta-resumen__num { font-size: 1.9rem; font-weight: 800; color: var(--color-danger); line-height: 1; white-space: nowrap; }
.alerta-resumen__texto { font-size: .88rem; color: var(--color-navy); font-weight: 600; }
.row-nivel--advertencia { background: rgba(255, 187, 0, .07); }
.row-nivel--critico { background: rgba(226, 72, 58, .07); }

/* Barra de filtros: fija arriba al hacer scroll, aplica a todo el reporte */
.asis__filtros {
  position: sticky; top: 0; z-index: 30;
  display: flex; flex-wrap: wrap; align-items: center; gap: .6rem;
  background: var(--color-white); border: 1px solid var(--color-gray-border);
  border-radius: var(--radius-md); padding: .7rem .9rem; box-shadow: var(--shadow-card);
}
.asis__filtros-limpiar { margin-left: auto; background: none; border: none; color: var(--color-blue-dark); font-weight: 700; font-size: .82rem; cursor: pointer; text-decoration: underline; padding: .3rem; }
.asis__filtros-limpiar:hover { color: var(--color-danger); }

/* Multiselect con buscador (Unidad, Nombre y Apellido, Mes, Dia) */
.ms { position: relative; }
.ms__btn {
  display: inline-flex; align-items: center; gap: .35rem; border: 1px solid var(--color-gray-border);
  background: var(--color-gray-bg-alt); color: var(--color-navy); font: inherit; font-weight: 700;
  font-size: .82rem; padding: .5rem .9rem; border-radius: var(--radius-pill); cursor: pointer;
}
.ms__btn:hover { border-color: var(--color-blue); }
.ms__btn.activo { background: rgba(0, 175, 242, .14); border-color: var(--color-blue); color: var(--color-blue-darker); }
.ms__panel {
  position: absolute; top: calc(100% + 6px); left: 0; min-width: 260px; max-width: 320px;
  background: var(--color-white); border: 1px solid var(--color-gray-border); border-radius: var(--radius-sm);
  box-shadow: 0 10px 28px rgba(0, 0, 0, .14); padding: .6rem; z-index: 40; display: none;
}
.ms__panel.abierto { display: block; }
.ms__buscar { width: 100%; box-sizing: border-box; padding: .4rem .6rem; border: 1px solid var(--color-gray-border); border-radius: 8px; font: inherit; font-size: .82rem; margin-bottom: .5rem; }
.ms__buscar:focus { outline: 2px solid var(--color-blue); outline-offset: 1px; }
.ms__lista { max-height: 240px; overflow-y: auto; display: flex; flex-direction: column; gap: .1rem; }
.ms__opcion { display: flex; align-items: center; gap: .5rem; padding: .3rem .35rem; border-radius: 6px; font-size: .82rem; cursor: pointer; }
.ms__opcion:hover { background: var(--color-gray-bg-alt); }
.ms__opcion input { accent-color: var(--color-blue); }
.ms__vacio { color: var(--color-gray-text); font-size: .8rem; padding: .3rem; }
"""

LOGO_PATH = PROJECT_ROOT / "logo.jpg"


def _logo_html() -> str:
    if not LOGO_PATH.exists():
        return ""
    data_uri = "data:image/jpeg;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f'<img class="asis__pin" src="{data_uri}" alt="Logo" width="44" height="44" />'

APP_JS = """
(function () {
  var D = window.__DATA__;
  var TODAS = D.filas;
  var FECHA_CORTE_ISO = D.fecha_corte_iso;
  var MESES_JS = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
  var AZULES = ['#00aff2', '#0093cc', '#3ec4f5', '#006b94', '#7cd8fb', '#004a66', '#ffbb00', '#5fc9ee', '#0093cc', '#003347'];
  // Paleta categorica para "Uso de permisos por tipo": tonos de azul solo
  // (AZULES) se confunden entre si en un donut con varias categorias. Esta
  // usa los dos colores de marca (azul, ambar) como ancla y suma matices bien
  // diferenciados entre si (verde, violeta, rosa, teal oscuro, naranja, gris)
  // para que cada tipo de permiso se distinga a simple vista.
  var PALETA_PERMISOS = ['#00aff2', '#ffbb00', '#10b981', '#8b5cf6', '#f43f5e', '#0f766e', '#f97316', '#64748b', '#0369a1'];
  var UMBRAL_ATRASOS = [4, 8];
  var UMBRAL_AUSENCIAS = [2, 3];
  var UMBRAL_INCOMPLETO = [2, 4];

  var filtros = { unidad: new Set(), nombre: new Set(), mes: new Set(), dia: new Set() };

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function mesDe(fIso) {
    var partes = fIso.split('-');
    return MESES_JS[parseInt(partes[1], 10)] + ' ' + partes[0];
  }
  function diaDe(fIso) { return fIso.split('-')[2]; }

  // ---------- Filtrado ----------
  function filasFiltradas() {
    return TODAS.filter(function (r) {
      if (filtros.unidad.size && !filtros.unidad.has(r.g)) return false;
      if (filtros.nombre.size && !filtros.nombre.has(r.n)) return false;
      if (filtros.mes.size && !filtros.mes.has(mesDe(r.f))) return false;
      if (filtros.dia.size && !filtros.dia.has(diaDe(r.f))) return false;
      return true;
    });
  }

  function contarPor(filas, claveFn) {
    var mapa = {};
    filas.forEach(function (r) { var k = claveFn(r); mapa[k] = (mapa[k] || 0) + 1; });
    var entradas = Object.keys(mapa).map(function (k) { return [k, mapa[k]]; });
    entradas.sort(function (a, b) { return b[1] - a[1]; });
    return { labels: entradas.map(function (e) { return e[0]; }), valores: entradas.map(function (e) { return e[1]; }) };
  }

  // ---------- Agregacion (misma logica que construir_datos_reporte en Python) ----------
  function recalcular(filas) {
    var laborable = filas.filter(function (r) { return !r.d && !r.fcp; });
    var esperados = laborable.length;
    var asistidos = laborable.filter(function (r) { return r.me; }).length;
    var ausentesFilas = laborable.filter(function (r) { return !r.me; });
    var pctAsistencia = esperados ? Math.round((asistidos / esperados) * 1000) / 10 : 0;

    // "No justificado" = igual criterio que las ausencias: Permiso debe ser
    // "Ninguno". Si la persona llego tarde con un permiso de fondo activo
    // (ej. Amamantamiento, que GeoVictoria marca en TODOS sus dias del mes)
    // no cuenta aca — verificado 18-ago-2026 contra un conteo manual del
    // usuario sobre el Excel (Atraso>0 y Permiso=Ninguno = 162 en agosto).
    var atrasosFilas = filas.filter(function (r) { return r.am > 0 && r.p === 'Ninguno'; });
    var atrasosMinTotal = Math.round(atrasosFilas.reduce(function (s, r) { return s + r.am; }, 0));

    var llegadasJustificadas = filas.filter(function (r) { return !r.d && r.lj; }).length;

    var concluidos = filas.filter(function (r) { return r.f < FECHA_CORTE_ISO; });
    var incompletoFilas = concluidos.filter(function (r) { return r.me && !r.ms && !r.d; });

    var horasTrabajadas = Math.round((filas.reduce(function (s, r) { return s + r.ht; }, 0) / 60) * 10) / 10;
    var dotacion = new Set(filas.map(function (r) { return r.id; })).size;

    var permisoFilas = filas.filter(function (r) { return r.fcp; });
    var permisosPorTipo = contarPor(permisoFilas, function (r) { return r.p; });

    var kpis = {
      dotacion: dotacion, pct_asistencia: pctAsistencia, asistidos: asistidos, esperados: esperados,
      atrasos_count: atrasosFilas.length, atrasos_min_total: atrasosMinTotal,
      llegadas_justificadas: llegadasJustificadas, ausentes: ausentesFilas.length,
      marcaje_incompleto: incompletoFilas.length, horas_trabajadas_total: horasTrabajadas,
      dias_con_permiso: permisoFilas.length,
    };

    // Evolucion diaria (dias laborables)
    var porFecha = {};
    laborable.forEach(function (r) {
      if (!porFecha[r.f]) porFecha[r.f] = { aTiempo: 0, atrasado: 0, ausente: 0 };
      if (!r.me) porFecha[r.f].ausente++;
      else if (r.am > 0 && r.p === 'Ninguno') porFecha[r.f].atrasado++;
      else porFecha[r.f].aTiempo++;
    });
    var fechasOrdenadas = Object.keys(porFecha).sort();
    var evolucion = { labels: [], aTiempo: [], atrasado: [], ausente: [] };
    fechasOrdenadas.forEach(function (f) {
      var partes = f.split('-');
      evolucion.labels.push(partes[2] + '-' + partes[1]);
      evolucion.aTiempo.push(porFecha[f].aTiempo);
      evolucion.atrasado.push(porFecha[f].atrasado);
      evolucion.ausente.push(porFecha[f].ausente);
    });

    // Detalle por area (Grupo / "Unidad")
    var porGrupo = {};
    filas.forEach(function (r) {
      if (!porGrupo[r.g]) porGrupo[r.g] = { ids: new Set(), atrasos: 0, minAtraso: 0, ht: 0, labEsp: 0, labAsis: 0 };
      var G = porGrupo[r.g];
      G.ids.add(r.id);
      if (r.am > 0 && r.p === 'Ninguno') { G.atrasos++; G.minAtraso += r.am; }
      G.ht += r.ht;
      if (!r.d && !r.fcp) { G.labEsp++; if (r.me) G.labAsis++; }
    });
    var detalleArea = Object.keys(porGrupo).map(function (g) {
      var G = porGrupo[g];
      var pct = G.labEsp ? Math.round((G.labAsis / G.labEsp) * 1000) / 10 : 0;
      return {
        grupo: g, dotacion: G.ids.size, pct_asistencia: pct,
        atrasos: G.atrasos, min_atraso: Math.round(G.minAtraso),
        ausencias: G.labEsp - G.labAsis, horas_trabajadas: Math.round((G.ht / 60) * 10) / 10,
      };
    }).sort(function (a, b) { return a.pct_asistencia - b.pct_asistencia; });

    var atrasosPorArea = detalleArea.slice()
      .filter(function (r) { return r.atrasos > 0; })
      .sort(function (a, b) { return b.atrasos - a.atrasos; })
      .map(function (r) { return { grupo: r.grupo, atrasos: r.atrasos }; });

    // Alertas por persona
    var porPersona = {};
    filas.forEach(function (r) {
      if (!porPersona[r.id]) porPersona[r.id] = { nombre: r.n, grupo: r.g, atrasos: 0, minAtraso: 0, ausencias: 0, incompleto: 0 };
    });
    atrasosFilas.forEach(function (r) { var P = porPersona[r.id]; P.atrasos++; P.minAtraso += r.am; });
    ausentesFilas.forEach(function (r) { porPersona[r.id].ausencias++; });
    incompletoFilas.forEach(function (r) { porPersona[r.id].incompleto++; });

    var rangoNivelOrden = { critico: 0, advertencia: 1, leve: 2 };
    var alertas = Object.keys(porPersona).map(function (id) {
      var P = porPersona[id];
      var nivel = 'ok';
      if (P.atrasos >= UMBRAL_ATRASOS[1] || P.ausencias >= UMBRAL_AUSENCIAS[1] || P.incompleto >= UMBRAL_INCOMPLETO[1]) nivel = 'critico';
      else if (P.atrasos >= UMBRAL_ATRASOS[0] || P.ausencias >= UMBRAL_AUSENCIAS[0] || P.incompleto >= UMBRAL_INCOMPLETO[0]) nivel = 'advertencia';
      // "Leve": tiene AL MENOS un indicador pero ninguno llega al umbral de
      // Advertencia. Sin esta categoria, al filtrar (ej. "Dia" a un solo
      // dia) alguien con 1-3 atrasos no aparecia en ningun lado de esta
      // tabla aunque el KPI de arriba mostrara atrasos > 0 — confundia,
      // parecia que la tabla no reflejaba los mismos datos que el resumen.
      else if (P.atrasos > 0 || P.ausencias > 0 || P.incompleto > 0) nivel = 'leve';
      var motivos = [];
      if (P.atrasos > 0) motivos.push('Atrasos no justificados (' + P.atrasos + ')');
      if (P.ausencias > 0) motivos.push('Ausencias injustificadas (' + P.ausencias + ')');
      if (P.incompleto > 0) motivos.push('Sin marcaje de salida (' + P.incompleto + ')');
      return {
        nombre: P.nombre, grupo: P.grupo, nivel: nivel, motivo: motivos.join(', '), atrasos: P.atrasos, min_atraso: Math.round(P.minAtraso),
        ausencias: P.ausencias, incompleto: P.incompleto,
        _total: P.atrasos + P.ausencias + P.incompleto, _rango: rangoNivelOrden[nivel],
      };
    }).filter(function (a) { return a.nivel !== 'ok'; })
      .sort(function (a, b) { return a._rango - b._rango || b._total - a._total; });

    return { kpis: kpis, evolucion: evolucion, atrasosPorArea: atrasosPorArea, permisosPorTipo: permisosPorTipo, detalleArea: detalleArea, alertas: alertas };
  }

  // ---------- Render: Resumen / KPIs ----------
  function kpi(label, value, cls) {
    return '<div class="kpi"><div class="label">' + label + '</div><div class="value ' + (cls || '') + '">' + value + '</div></div>';
  }

  function renderResumen(K) {
    var pctAus = K.esperados ? Math.round((K.ausentes / K.esperados) * 1000) / 10 : 0;
    var barraAsis = document.getElementById('barra-asistencia');
    var barraAus = document.getElementById('barra-ausencia');
    barraAsis.style.width = K.pct_asistencia + '%';
    barraAus.style.width = Math.max(0, 100 - K.pct_asistencia) + '%';
    document.getElementById('barra-asistencia-txt').textContent = K.pct_asistencia >= 8 ? K.pct_asistencia + '% Asistencia' : '';
    document.getElementById('barra-ausencia-txt').textContent = (100 - K.pct_asistencia) >= 8 ? pctAus + '% Ausencia' : '';

    document.getElementById('kpis').innerHTML = [
      kpi('Dotacion', K.dotacion),
      kpi('% Asistencia', K.pct_asistencia + '%'),
      kpi('Llegadas justificadas', K.llegadas_justificadas),
      kpi('Atrasos no justificados', K.atrasos_count, 'danger'),
      kpi('Minutos de atraso', K.atrasos_min_total, 'danger'),
      kpi('Ausencias injustificadas', K.ausentes, 'danger'),
      kpi('Dias sin marcaje de salida', K.marcaje_incompleto, 'danger'),
    ].join('');
  }

  // ---------- Render: graficos (se actualizan in-place, sin recrear) ----------
  // Barras apiladas en vez de linea: con pocos dias filtrados (ej. un solo
  // "Dia" seleccionado) una linea/area queda como un par de puntos sueltos
  // pegados a la izquierda del grafico, casi invisible. Una barra apilada
  // se centra sola sin importar cuantas categorias haya, asi que se ve bien
  // tanto con 1 dia como con el mes completo.
  var chartEvolucion = new Chart(document.getElementById('chart-evolucion'), {
    type: 'bar',
    data: {
      labels: [],
      datasets: [
        { label: 'A tiempo', data: [], backgroundColor: '#00aff2', maxBarThickness: 60 },
        { label: 'Atrasado', data: [], backgroundColor: '#ffbb00', maxBarThickness: 60 },
        { label: 'Ausente', data: [], backgroundColor: '#e2483a', maxBarThickness: 60 },
      ],
    },
    plugins: [ChartDataLabels],
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { stacked: true },
        y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
      },
      plugins: {
        legend: { position: 'bottom' },
        datalabels: {
          // Un solo % de asistencia por dia, mostrado dentro del segmento
          // "A tiempo" (el mas grande de la barra apilada) — se calcula
          // sumando A tiempo + Atrasado (ambos marcaron entrada) sobre el
          // total del dia, mismo criterio que el % Asistencia del resumen.
          display: function (ctx) { return ctx.datasetIndex === 0; },
          color: '#ffffff', font: { weight: '700', size: 10 },
          anchor: 'center', align: 'center',
          formatter: function (value, ctx) {
            var atrasado = ctx.chart.data.datasets[1].data[ctx.dataIndex] || 0;
            var ausente = ctx.chart.data.datasets[2].data[ctx.dataIndex] || 0;
            var total = value + atrasado + ausente;
            if (!total) return '';
            var pct = Math.round(((value + atrasado) / total) * 1000) / 10;
            return pct + '%';
          },
        },
      },
    },
  });

  var chartAtrasosArea = new Chart(document.getElementById('chart-atrasos-area'), {
    type: 'bar',
    data: { labels: [], datasets: [{ label: 'Atrasos', data: [], backgroundColor: '#00aff2', borderRadius: 6 }] },
    plugins: [ChartDataLabels],
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
      plugins: {
        legend: { display: false },
        datalabels: {
          color: '#ffffff', font: { weight: '700', size: 11 }, anchor: 'center', align: 'center',
          formatter: function (value) { return value; },
        },
      },
    },
  });

  var chartPermisos = new Chart(document.getElementById('chart-permisos'), {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [], backgroundColor: function (ctx) { return PALETA_PERMISOS[ctx.dataIndex % PALETA_PERMISOS.length]; } }] },
    plugins: [ChartDataLabels],
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: {
            boxWidth: 12, font: { size: 11 },
            generateLabels: function (chart) {
              var data = chart.data;
              if (!data.labels.length) return [];
              var valores = data.datasets[0].data;
              return data.labels.map(function (label, i) {
                return { text: label + ' (' + valores[i] + ')', fillStyle: PALETA_PERMISOS[i % PALETA_PERMISOS.length], strokeStyle: PALETA_PERMISOS[i % PALETA_PERMISOS.length], index: i };
              });
            },
          },
        },
        datalabels: {
          color: '#ffffff',
          font: { weight: '700', size: 11 },
          formatter: function (value, ctx) {
            var total = ctx.chart.data.datasets[0].data.reduce(function (a, b) { return a + b; }, 0);
            if (!total) return '';
            var pct = Math.round((value / total) * 100);
            return pct >= 5 ? pct + '%' : '';
          },
        },
      },
    },
  });

  function actualizarGraficos(res) {
    chartEvolucion.data.labels = res.evolucion.labels;
    chartEvolucion.data.datasets[0].data = res.evolucion.aTiempo;
    chartEvolucion.data.datasets[1].data = res.evolucion.atrasado;
    chartEvolucion.data.datasets[2].data = res.evolucion.ausente;
    chartEvolucion.update();

    chartAtrasosArea.data.labels = res.atrasosPorArea.map(function (r) { return r.grupo; });
    chartAtrasosArea.data.datasets[0].data = res.atrasosPorArea.map(function (r) { return r.atrasos; });
    // Alto dinamico: ~38px por barra, minimo 380px (10 filas) — el contenedor
    // .asis__chart-scroll queda fijo en 380px con scroll, asi siempre se ven
    // ~10 areas a la vez pero se puede desplazar para ver el resto.
    document.getElementById('chart-atrasos-area-inner').style.height = Math.max(380, res.atrasosPorArea.length * 38) + 'px';
    chartAtrasosArea.resize();
    chartAtrasosArea.update();

    chartPermisos.data.labels = res.permisosPorTipo.labels;
    chartPermisos.data.datasets[0].data = res.permisosPorTipo.valores;
    chartPermisos.update();
  }

  // ---------- Render: tablas ordenables ----------
  var etiquetaNivel = { critico: 'Critico', advertencia: 'Advertencia', leve: 'Leve' };
  var rangoNivel = { critico: 0, advertencia: 1, leve: 2 };

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
        if (tipo === 'nivel') { va = rangoNivel[va]; vb = rangoNivel[vb]; }
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
            return '<td><span class="badge-nivel badge-nivel--' + val + '">' + (etiquetaNivel[val] || val) + '</span></td>';
          }
          if (formatos && formatos[key]) val = formatos[key](val);
          var cls = (key === 'ausencias' || key === 'atrasos' || key === 'min_atraso' || key === 'incompleto') && Number(f[key]) > 0 ? ' class="danger-text"' : '';
          return '<td' + cls + '>' + val + '</td>';
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

  var tablaArea = crearTabla('tabla-area', { pct_asistencia: function (v) { return v + '%'; } });
  var tablaAlertas = crearTabla('tabla-alertas');

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

    return { limpiar: function () { seleccion.clear(); actualizarBoton(); pintarLista(buscar.value); } };
  }

  function renderAlertaResumen(alertas, dotacion) {
    document.getElementById('alerta-resumen-num').textContent = alertas.length + ' de ' + dotacion;
    document.getElementById('alerta-resumen-texto').textContent =
      alertas.length === 1
        ? '1 persona presenta atrasos no justificados, ausencias injustificadas o dias sin marcaje de salida.'
        : alertas.length + ' personas presentan atrasos no justificados, ausencias injustificadas o dias sin marcaje de salida.';
  }

  function actualizar() {
    var filas = filasFiltradas();
    var res = recalcular(filas);
    renderResumen(res.kpis);
    renderAlertaResumen(res.alertas, res.kpis.dotacion);
    actualizarGraficos(res);
    tablaArea.actualizar(res.detalleArea);
    tablaAlertas.actualizar(res.alertas);
  }

  var msUnidad = crearMultiSelect(document.getElementById('filtro-unidad'), 'Unidad', D.opciones.unidades, function (sel) { filtros.unidad = sel; actualizar(); });
  var msNombre = crearMultiSelect(document.getElementById('filtro-nombre'), 'Nombre y Apellido', D.opciones.nombres, function (sel) { filtros.nombre = sel; actualizar(); });
  var msMes = crearMultiSelect(document.getElementById('filtro-mes'), 'Mes', D.opciones.meses, function (sel) { filtros.mes = sel; actualizar(); });
  var msDia = crearMultiSelect(document.getElementById('filtro-dia'), 'Dia', D.opciones.dias, function (sel) { filtros.dia = sel; actualizar(); });

  document.getElementById('btn-limpiar-filtros').addEventListener('click', function () {
    filtros = { unidad: new Set(), nombre: new Set(), mes: new Set(), dia: new Set() };
    msUnidad.limpiar(); msNombre.limpiar(); msMes.limpiar(); msDia.limpiar();
    actualizar();
  });

  actualizar();
})();
"""


def generar_reporte_html(ruta_excel: Path, destino: Path | None = None) -> Path:
    df = cargar_datos(ruta_excel)
    datos = construir_datos_reporte(df)
    periodo = _mes_periodo(df)

    if destino is None:
        carpeta = PROJECT_ROOT / "data" / "reportes"
        carpeta.mkdir(parents=True, exist_ok=True)
        ts = pd.Timestamp.now().strftime("%Y-%m-%d_%H%M%S")
        destino = carpeta / f"Asistencia_{periodo.replace(' ', '_')}_{ts}.html"

    chartjs = CHARTJS_PATH.read_text(encoding="utf-8")
    chartjs_datalabels = CHARTJS_DATALABELS_PATH.read_text(encoding="utf-8")

    html = HTML_TEMPLATE.format(
        periodo=periodo,
        pin_svg=_logo_html(),
        fecha_corte=datos["fecha_corte"],
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
    ruta = Path(archivo) if archivo else EJEMPLO
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro el archivo Excel: {ruta}")
    destino = Path(salida) if salida else None
    resultado = generar_reporte_html(ruta, destino)
    print(f"Reporte generado: {resultado}")


if __name__ == "__main__":
    arg_archivo = sys.argv[1] if len(sys.argv) > 1 else None
    arg_salida = sys.argv[2] if len(sys.argv) > 2 else None
    main(arg_archivo, arg_salida)
