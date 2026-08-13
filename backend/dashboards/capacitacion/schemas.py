from datetime import date
from typing import Optional

from pydantic import BaseModel


class ActualizacionOut(BaseModel):
    dotacion: int
    nuevos_ingresos: int
    cambios_cargo: int
    cargos_revisar: int
    backup: Optional[str] = None


class DotacionOut(BaseModel):
    model_config = {"from_attributes": True}

    Cod_Personal: Optional[int] = None
    Nombre_Completo: Optional[str] = None
    Area_Personal: Optional[str] = None
    Sociedad: Optional[str] = None
    Unidad_Organizativa: Optional[str] = None
    Funcion: Optional[str] = None
    Gerencia: Optional[str] = None
    Subgerencia: Optional[str] = None
    Fecha_Ingreso: Optional[date] = None
    Nombre_Superior: Optional[str] = None
    Nacionalidad: Optional[str] = None
    Mail: Optional[str] = None
    Clasificacion: Optional[str] = None
    Mes_Reporte: Optional[int] = None
    Anio_Reporte: Optional[int] = None


class CambioCargoOut(DotacionOut):
    Cargo_Anterior: Optional[str] = None


class CargoRevisarOut(BaseModel):
    model_config = {"from_attributes": True}

    Funcion: Optional[str] = None
    Cantidad_Personas: Optional[int] = None


class ProcedimientoOut(BaseModel):
    model_config = {"from_attributes": True}

    Funcion: str
    Codigos: str


class ProcedimientoIn(BaseModel):
    funcion: str
    codigos: str
