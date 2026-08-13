import { apiGet, apiUpload } from "./client";

export interface SobretiempoFilters {
  anio?: number;
  mes?: number;
  sociedad?: string;
  gerencia?: string;
  subgerencia?: string;
  unidad?: string;
  ceco?: string;
  cuenta?: number;
}

export interface ResumenGerencia {
  Gerencia: string;
  Subgerencia: string;
  Anio: number;
  Mes_Num: number;
  Mes_Nombre: string;
  Mes_Orden: string;
  Mes_Cerrado: boolean;
  Presupuesto_Total_Anual: number;
  Importe_Real_Mes: number;
  Real_Acumulado: number;
  Saldo_Disponible: number;
  Pct_Ocupado: number | null;
  Trabajadores_Con_HE_Mes: number;
  Trabajadores_Con_HE_Acumulado: number;
  Estado: string;
}

export interface Resumen {
  Sociedad: string;
  Ceco: string;
  Cuenta_Contable: number;
  Gerencia: string;
  Subgerencia: string;
  Unidad_Organizativa: string;
  Anio: number;
  Mes_Num: number;
  Mes_Nombre: string;
  Mes_Cerrado: boolean;
  Importe_Real: number;
  Horas_Real: number;
  Presupuesto: number;
  Saldo_Mes: number;
  Pct_Ejecucion_Mes: number | null;
  Estado_Mes: string;
  Real_Acumulado: number;
  Presupuesto_Acumulado: number;
  Saldo_Acumulado: number;
  Pct_Ejecucion_Acumulado: number | null;
  Estado_Acumulado: string;
  Con_Presupuesto_Asignado: boolean;
}

export interface Detalle {
  Cod_SAP: number;
  Nombre_Personal: string;
  Sociedad: string;
  Gerencia: string;
  Subgerencia: string;
  Unidad_Organizativa: string;
  Cargo: string;
  Ceco: string;
  Cuenta_Contable: number;
  Concepto: string;
  Cantidad_Horas: number;
  Importe: number;
  Anio: number;
  Mes_Num: number;
  Mes_Nombre: string;
  Con_Presupuesto_Asignado: boolean;
}

export function getResumenGerencia(filters: SobretiempoFilters = {}): Promise<ResumenGerencia[]> {
  return apiGet<ResumenGerencia[]>("/dashboards/sobretiempo/resumen-gerencia", { ...filters });
}

export function getResumen(filters: SobretiempoFilters = {}): Promise<Resumen[]> {
  return apiGet<Resumen[]>("/dashboards/sobretiempo/resumen", { ...filters });
}

export function getDetalle(filters: SobretiempoFilters = {}): Promise<Detalle[]> {
  return apiGet<Detalle[]>("/dashboards/sobretiempo/detalle", { ...filters });
}

export interface ResultadoActualizacion {
  detalle: number;
  presupuesto: number;
  resumen: number;
  resumen_gerencia: number;
  backup: string | null;
}

export function actualizarDatos(archivo: File): Promise<ResultadoActualizacion> {
  const formData = new FormData();
  formData.append("archivo", archivo);
  return apiUpload<ResultadoActualizacion>("/dashboards/sobretiempo/actualizar", formData);
}
