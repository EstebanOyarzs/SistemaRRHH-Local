from sqlalchemy import create_engine, text

from backend.config import PROJECT_ROOT

# DB propia del dashboard de Capacitacion, separada de sistema.db (auth) y
# de sobretiempo.db. Vive fisicamente dentro de Capacitacion/.
DB_DIR = PROJECT_ROOT / "Capacitacion" / "data"
DB_PATH = DB_DIR / "capacitacion.db"
DB_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

# Nombres de tabla con prefijo del dashboard. capacitacion_procedimientos es
# la unica que NO se reemplaza en cada carga mensual (es la tabla maestra
# Funcion -> Codigos, editable desde la UI) — las otras 2 se recalculan por
# completo cada vez que se sube un par de dotaciones. La Clasificacion y los
# "cargos a revisar" NO se guardan como columnas/tabla fijas — se calculan
# en cada lectura haciendo JOIN contra capacitacion_procedimientos (ver
# router.py), para que editar la tabla maestra se refleje al instante en
# todas las vistas sin tener que volver a subir las dotaciones.
TABLE_PROCEDIMIENTOS = "capacitacion_procedimientos"
TABLE_DOTACION = "capacitacion_dotacion"
TABLE_NUEVOS_INGRESOS = "capacitacion_nuevos_ingresos"
TABLE_CAMBIOS_CARGO = "capacitacion_cambios_cargo"

# La tabla maestra se crea (si no existe) apenas se importa este modulo, con
# Funcion como PRIMARY KEY para poder hacer INSERT OR REPLACE al editarla
# desde la UI. El sembrado de datos iniciales (normalizar.sembrar_procedimientos_si_vacia)
# se dispara aparte, desde router.py, para no mezclar pandas/Excel en este
# archivo de solo-schema.
with engine.begin() as _conn:
    _conn.execute(text(
        f"CREATE TABLE IF NOT EXISTS {TABLE_PROCEDIMIENTOS} "
        "(Funcion TEXT PRIMARY KEY, Codigos TEXT NOT NULL)"
    ))
