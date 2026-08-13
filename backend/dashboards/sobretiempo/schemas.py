from datetime import date
from typing import Optional

from pydantic import BaseModel


class DetalleOut(BaseModel):
    model_config = {"from_attributes": True}

    Cod_SAP: Optional[int] = None
    Nombre_Personal: Optional[str] = None
    RUT: Optional[str] = None
    Sociedad: Optional[str] = None
    Division_Personal: Optional[str] = None
    Gerencia: Optional[str] = None
    Subgerencia: Optional[str] = None
    Unidad_Organizativa: Optional[str] = None
    Cargo: Optional[str] = None
    Area_Personal: Optional[str] = None
    Ceco: Optional[str] = None
    Cuenta_Contable: Optional[int] = None
    OI: Optional[str] = None
    PEP: Optional[str] = None
    Codigo_Concepto: Optional[float] = None
    Concepto: Optional[str] = None
    Clasif_Haber: Optional[str] = None
    Clasificacion: Optional[str] = None
    Cantidad_Horas: Optional[float] = None
    Importe: Optional[float] = None
    Validacion: Optional[str] = None
    Anio: Optional[int] = None
    Mes_Nombre: Optional[str] = None
    Mes_Num: Optional[int] = None
    Mes_Orden: Optional[str] = None
    Fecha: Optional[date] = None
    Subcuenta: Optional[str] = None
    Con_Presupuesto_Asignado: Optional[bool] = None
    Mes_Cerrado: Optional[bool] = None


class PresupuestoOut(BaseModel):
    model_config = {"from_attributes": True}

    Ceco: Optional[str] = None
    Cuenta_Contable: Optional[int] = None
    Subcuenta: Optional[str] = None
    Sociedad: Optional[str] = None
    Gerencia: Optional[str] = None
    Subgerencia: Optional[str] = None
    Unidad_Organizativa: Optional[str] = None
    Anio: Optional[int] = None
    Mes_Num: Optional[int] = None
    Mes_Nombre: Optional[str] = None
    Mes_Orden: Optional[str] = None
    Fecha: Optional[date] = None
    Presupuesto: Optional[float] = None


class ResumenOut(BaseModel):
    model_config = {"from_attributes": True}

    Sociedad: Optional[str] = None
    Ceco: Optional[str] = None
    Cuenta_Contable: Optional[int] = None
    Subcuenta: Optional[str] = None
    Gerencia: Optional[str] = None
    Subgerencia: Optional[str] = None
    Unidad_Organizativa: Optional[str] = None
    Anio: Optional[int] = None
    Mes_Num: Optional[int] = None
    Mes_Nombre: Optional[str] = None
    Mes_Orden: Optional[str] = None
    Fecha: Optional[date] = None
    Mes_Cerrado: Optional[bool] = None
    Importe_Real: Optional[float] = None
    Horas_Real: Optional[float] = None
    Presupuesto: Optional[float] = None
    Saldo_Mes: Optional[float] = None
    Pct_Ejecucion_Mes: Optional[float] = None
    Estado_Mes: Optional[str] = None
    Real_Acumulado: Optional[float] = None
    Horas_Real_Acumulado: Optional[float] = None
    Presupuesto_Acumulado: Optional[float] = None
    Saldo_Acumulado: Optional[float] = None
    Pct_Ejecucion_Acumulado: Optional[float] = None
    Estado_Acumulado: Optional[str] = None
    Con_Presupuesto_Asignado: Optional[bool] = None


class ResumenGerenciaOut(BaseModel):
    model_config = {"from_attributes": True}

    Gerencia: Optional[str] = None
    Subgerencia: Optional[str] = None
    Anio: Optional[int] = None
    Mes_Num: Optional[int] = None
    Mes_Nombre: Optional[str] = None
    Mes_Orden: Optional[str] = None
    Fecha: Optional[date] = None
    Mes_Cerrado: Optional[bool] = None
    Presupuesto_Total_Anual: Optional[float] = None
    Importe_Real_Mes: Optional[float] = None
    Real_Acumulado: Optional[float] = None
    Saldo_Disponible: Optional[float] = None
    Pct_Ocupado: Optional[float] = None
    Trabajadores_Con_HE_Mes: Optional[int] = None
    Trabajadores_Con_HE_Acumulado: Optional[int] = None
    Estado: Optional[str] = None
