from sqlalchemy import create_engine

from backend.config import PROJECT_ROOT

# DB propia del dashboard de Sobretiempo, separada de data/sistema.db (que
# solo tiene auth). Vive fisicamente dentro de Sobretiempo/ junto con el
# script normalizador que la alimenta cada mes.
DB_DIR = PROJECT_ROOT / "Sobretiempo" / "data"
DB_PATH = DB_DIR / "sobretiempo.db"
DB_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)

# Nombres de tabla con prefijo del dashboard al que pertenecen (convencion:
# cada dashboard nuevo trae sus propias tablas independientes).
TABLE_DETALLE = "sobretiempo_detalle"
TABLE_PRESUPUESTO = "sobretiempo_presupuesto"
TABLE_RESUMEN = "sobretiempo_resumen"
TABLE_RESUMEN_GERENCIA = "sobretiempo_resumen_gerencia"
