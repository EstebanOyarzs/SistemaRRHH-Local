import { apiGet, apiPut, apiUpload, ApiError, getToken } from "./client";

export interface Dotacion {
  Cod_Personal: number;
  Nombre_Completo: string;
  Area_Personal: string;
  Sociedad: string;
  Unidad_Organizativa: string;
  Funcion: string;
  Gerencia: string;
  Subgerencia: string;
  Fecha_Ingreso: string;
  Nombre_Superior: string;
  Nacionalidad: string;
  Mail: string;
  Clasificacion: string;
  Mes_Reporte: number;
  Anio_Reporte: number;
}

export interface CambioCargo extends Dotacion {
  Cargo_Anterior: string;
}

export interface CargoRevisar {
  Funcion: string;
  Cantidad_Personas: number;
}

export interface Procedimiento {
  Funcion: string;
  Codigos: string;
}

export interface ResultadoActualizacion {
  dotacion: number;
  nuevos_ingresos: number;
  cambios_cargo: number;
  cargos_revisar: number;
  backup: string | null;
}

export function getDotacion(): Promise<Dotacion[]> {
  return apiGet<Dotacion[]>("/dashboards/capacitacion/dotacion");
}

export function getNuevosIngresos(): Promise<Dotacion[]> {
  return apiGet<Dotacion[]>("/dashboards/capacitacion/nuevos-ingresos");
}

export function getCambiosCargo(): Promise<CambioCargo[]> {
  return apiGet<CambioCargo[]>("/dashboards/capacitacion/cambios-cargo");
}

export function getCargosRevisar(): Promise<CargoRevisar[]> {
  return apiGet<CargoRevisar[]>("/dashboards/capacitacion/cargos-revisar");
}

export function getProcedimientos(): Promise<Procedimiento[]> {
  return apiGet<Procedimiento[]>("/dashboards/capacitacion/procedimientos");
}

export function guardarProcedimiento(funcion: string, codigos: string): Promise<Procedimiento> {
  return apiPut<Procedimiento>("/dashboards/capacitacion/procedimientos", { funcion, codigos });
}

export function actualizarDatos(
  archivoActual: File,
  archivoAnterior: File,
  mes: number,
  anio: number,
): Promise<ResultadoActualizacion> {
  const formData = new FormData();
  formData.append("archivo_actual", archivoActual);
  formData.append("archivo_anterior", archivoAnterior);
  formData.append("mes", String(mes));
  formData.append("anio", String(anio));
  return apiUpload<ResultadoActualizacion>("/dashboards/capacitacion/actualizar", formData);
}

// El export a Excel devuelve un binario (no JSON), asi que no puede pasar
// por el helper `request()` de client.ts (siempre parsea JSON) — se hace un
// fetch aparte, pero reusando el mismo token/base URL.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function descargarReporteExcel(): Promise<void> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}/dashboards/capacitacion/exportar-excel`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? `Error ${response.status}`);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "Reporte para capacitaciones.xlsx";

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
