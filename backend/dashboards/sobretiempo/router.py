import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from backend.auth.dependencies import get_current_user, require_roles
from backend.config import PROJECT_ROOT
from backend.database.models import User, UserRole
from backend.dashboards.sobretiempo.db import (
    TABLE_DETALLE,
    TABLE_PRESUPUESTO,
    TABLE_RESUMEN,
    TABLE_RESUMEN_GERENCIA,
    engine,
)
from backend.dashboards.sobretiempo.normalizar import procesar_archivo
from backend.dashboards.sobretiempo.schemas import (
    ActualizacionOut,
    DetalleOut,
    PresupuestoOut,
    ResumenGerenciaOut,
    ResumenOut,
)

UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads" / "sobretiempo"

router = APIRouter(prefix="/dashboards/sobretiempo", tags=["dashboards:sobretiempo"])

NO_DATA_ERROR = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=(
        "Todavia no se cargo ningun archivo de sobretiempo. "
        "Correr Sobretiempo/normalizar_sobretiempo.py primero."
    ),
)


# Columnas validas por tabla: resumen_gerencia solo esta agregada a nivel
# Gerencia+Subgerencia+Mes, no tiene Sociedad/Unidad/Ceco/Cuenta. Filtrar por
# esas columnas ahi directamente rompería el SQL, asi que se ignoran para esa
# tabla en vez de fallar.
_ORG_COLUMNS = {"Anio", "Mes_Num", "Sociedad", "Gerencia", "Subgerencia", "Unidad_Organizativa", "Ceco", "Cuenta_Contable"}
TABLE_COLUMNS: dict[str, set[str]] = {
    TABLE_DETALLE: _ORG_COLUMNS,
    TABLE_PRESUPUESTO: _ORG_COLUMNS,
    TABLE_RESUMEN: _ORG_COLUMNS,
    TABLE_RESUMEN_GERENCIA: {"Anio", "Mes_Num", "Gerencia", "Subgerencia"},
}


@dataclass
class SobretiempoFilters:
    anio: Optional[int] = None
    mes: Optional[int] = None
    sociedad: Optional[str] = None
    gerencia: Optional[str] = None
    subgerencia: Optional[str] = None
    unidad: Optional[str] = None
    ceco: Optional[str] = None
    cuenta: Optional[int] = None

    def as_columns(self) -> dict[str, object]:
        cols = {
            "anio": "Anio",
            "mes": "Mes_Num",
            "sociedad": "Sociedad",
            "gerencia": "Gerencia",
            "subgerencia": "Subgerencia",
            "unidad": "Unidad_Organizativa",
            "ceco": "Ceco",
            "cuenta": "Cuenta_Contable",
        }
        return {cols[k]: v for k, v in vars(self).items() if v is not None}


def _query(table: str, filters: SobretiempoFilters) -> list[dict]:
    params = {col: v for col, v in filters.as_columns().items() if col in TABLE_COLUMNS[table]}
    sql = f"SELECT * FROM {table}"
    if params:
        sql += " WHERE " + " AND ".join(f"{col} = :{col}" for col in params)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
    except OperationalError:
        raise NO_DATA_ERROR
    return [dict(row) for row in rows]


@router.get("/resumen-gerencia", response_model=list[ResumenGerenciaOut])
def get_resumen_gerencia(
    filters: SobretiempoFilters = Depends(),
    _user: User = Depends(get_current_user),
):
    return _query(TABLE_RESUMEN_GERENCIA, filters)


@router.get("/resumen", response_model=list[ResumenOut])
def get_resumen(
    filters: SobretiempoFilters = Depends(),
    _user: User = Depends(get_current_user),
):
    return _query(TABLE_RESUMEN, filters)


@router.get("/detalle", response_model=list[DetalleOut])
def get_detalle(
    filters: SobretiempoFilters = Depends(),
    _user: User = Depends(get_current_user),
):
    return _query(TABLE_DETALLE, filters)


@router.get("/presupuesto", response_model=list[PresupuestoOut])
def get_presupuesto(
    filters: SobretiempoFilters = Depends(),
    _user: User = Depends(get_current_user),
):
    return _query(TABLE_PRESUPUESTO, filters)


@router.post("/actualizar", response_model=ActualizacionOut)
async def actualizar_datos(
    archivo: UploadFile = File(...),
    _admin: User = Depends(require_roles(UserRole.ADMINISTRADOR)),
):
    """Sube el Excel mensual de "Control de Sobretiempo", lo normaliza y
    reemplaza las 4 tablas — respaldando antes la base anterior. Solo admin,
    porque pisa los datos que ven todos los usuarios del dashboard."""
    if not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx)")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = UPLOADS_DIR / f"{timestamp}_{archivo.filename}"
    with destino.open("wb") as f:
        shutil.copyfileobj(archivo.file, f)

    try:
        resultado = procesar_archivo(destino)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "No se pudo procesar el archivo — revisa que tenga las hojas "
                f"'DETALLE 2,0' y 'PPTO 2026' con el formato esperado. Detalle: {exc}"
            ),
        )

    return resultado
