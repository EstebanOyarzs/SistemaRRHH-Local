import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Bar, Doughnut, Line } from "react-chartjs-2";
import ChartDataLabels, { type Context } from "chartjs-plugin-datalabels";
import { CHART_COLORS } from "../charts/registerCharts";
import { SearchableSelect } from "../components/SearchableSelect";
import {
  actualizarDatos,
  getDetalle,
  getResumen,
  type Detalle,
  type Resumen,
  type ResultadoActualizacion,
} from "../api/sobretiempo";
import type { UserRole } from "../api/auth";
import { ApiError } from "../api/client";
import { formatCurrency } from "../utils/format";
import { exportarDashboardHtml } from "../utils/exportarHtml";
import { ordenarFilas, type Columna } from "../utils/tablas";
import "./SobretiempoDashboardPage.css";

function sum(values: number[]): number {
  return values.reduce((acc, v) => acc + v, 0);
}

function formatCompactCurrency(value: number): string {
  if (!value) return "";
  return `$${Math.round(value / 1_000_000)}M`;
}

function groupSum<T>(rows: T[], keyFn: (row: T) => string, valueFn: (row: T) => number): Map<string, number> {
  const map = new Map<string, number>();
  for (const row of rows) {
    const key = keyFn(row);
    map.set(key, (map.get(key) ?? 0) + valueFn(row));
  }
  return map;
}

function uniqueSorted<T>(values: T[]): T[] {
  return Array.from(new Set(values)).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

const MESES_ORDEN = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

type DimensionSaldo = "sociedad" | "gerencia" | "subgerencia" | "unidad" | "cuenta";

const DIMENSIONES_SALDO: { value: DimensionSaldo; label: string; keyFn: (r: Resumen) => string }[] = [
  { value: "sociedad", label: "Sociedades", keyFn: (r) => r.Sociedad },
  { value: "gerencia", label: "Gerencias", keyFn: (r) => r.Gerencia },
  { value: "subgerencia", label: "Subgerencias", keyFn: (r) => r.Subgerencia },
  { value: "unidad", label: "Unidades", keyFn: (r) => r.Unidad_Organizativa },
  { value: "cuenta", label: "Cuentas", keyFn: (r) => String(r.Cuenta_Contable) },
];

// Saldo disponible (presupuesto anual - real acumulado al ultimo mes cerrado)
// agrupado por la dimension elegida en el selector.
function agregarSaldoPorDimension(
  rows: Resumen[],
  keyFn: (r: Resumen) => string,
  ultimoMesCerrado: number,
): [string, number][] {
  const presupuesto = groupSum(rows, keyFn, (r) => r.Presupuesto);
  const real = groupSum(
    rows.filter((r) => r.Mes_Num === ultimoMesCerrado),
    keyFn,
    (r) => r.Real_Acumulado,
  );
  const claves = new Set([...presupuesto.keys(), ...real.keys()]);
  return Array.from(claves)
    .map((k) => [k, (presupuesto.get(k) ?? 0) - (real.get(k) ?? 0)] as [string, number])
    .sort((a, b) => a[1] - b[1]);
}

const COLUMNAS_DETALLE: Columna<Resumen>[] = [
  { id: "sociedad", label: "Sociedad", valor: (r) => r.Sociedad, render: (r) => r.Sociedad },
  { id: "gerencia", label: "Gerencia", valor: (r) => r.Gerencia, render: (r) => r.Gerencia },
  { id: "subgerencia", label: "Subgerencia", valor: (r) => r.Subgerencia, render: (r) => r.Subgerencia },
  { id: "unidad", label: "Unidad", valor: (r) => r.Unidad_Organizativa, render: (r) => r.Unidad_Organizativa },
  { id: "ceco", label: "Ceco", valor: (r) => r.Ceco, render: (r) => r.Ceco },
  { id: "cuenta", label: "Cuenta", valor: (r) => r.Cuenta_Contable, render: (r) => r.Cuenta_Contable },
  {
    id: "presupuesto",
    label: "Presupuesto acum.",
    valor: (r) => r.Presupuesto_Acumulado,
    render: (r) => formatCurrency(r.Presupuesto_Acumulado),
  },
  {
    id: "real",
    label: "Real acum.",
    valor: (r) => r.Real_Acumulado,
    render: (r) => formatCurrency(r.Real_Acumulado),
  },
  {
    id: "saldo",
    label: "Saldo acum.",
    valor: (r) => r.Saldo_Acumulado,
    render: (r) => (
      <span className={r.Saldo_Acumulado < 0 ? "negativo" : "positivo"}>{formatCurrency(r.Saldo_Acumulado)}</span>
    ),
  },
  { id: "estado", label: "Estado", valor: (r) => r.Estado_Acumulado, render: (r) => r.Estado_Acumulado },
];

const COLUMNAS_TRANSACCIONES: Columna<Detalle>[] = [
  { id: "nombre", label: "Nombre", valor: (d) => d.Nombre_Personal, render: (d) => d.Nombre_Personal },
  { id: "cargo", label: "Cargo", valor: (d) => d.Cargo, render: (d) => d.Cargo },
  { id: "gerencia", label: "Gerencia", valor: (d) => d.Gerencia, render: (d) => d.Gerencia },
  { id: "concepto", label: "Concepto", valor: (d) => d.Concepto, render: (d) => d.Concepto },
  { id: "horas", label: "Horas", valor: (d) => d.Cantidad_Horas, render: (d) => d.Cantidad_Horas },
  { id: "importe", label: "Importe", valor: (d) => d.Importe, render: (d) => formatCurrency(d.Importe) },
];

type DimKey = "mes" | "sociedad" | "gerencia" | "subgerencia" | "unidad" | "ceco" | "cuenta";

function extraerValoresResumen(row: Resumen): Record<DimKey, string> {
  return {
    mes: row.Mes_Nombre,
    sociedad: row.Sociedad,
    gerencia: row.Gerencia,
    subgerencia: row.Subgerencia,
    unidad: row.Unidad_Organizativa,
    ceco: row.Ceco,
    cuenta: String(row.Cuenta_Contable),
  };
}

function extraerValoresDetalle(row: Detalle): Record<DimKey, string> {
  return {
    mes: row.Mes_Nombre,
    sociedad: row.Sociedad,
    gerencia: row.Gerencia,
    subgerencia: row.Subgerencia,
    unidad: row.Unidad_Organizativa,
    ceco: row.Ceco,
    cuenta: String(row.Cuenta_Contable),
  };
}

// Compara una fila contra los filtros activos. Si se pasa "exclude", esa
// dimension no se evalua (sirve para calcular las opciones de UN filtro sin
// que se autoelimine sus propias opciones). Sin "exclude", filtra por TODAS
// las dimensiones activas — es lo que se usa para armar los datos reales,
// tanto pidiendolos al backend como (en un HTML exportado) filtrando en el
// propio navegador contra el dataset completo embebido.
function coincideConFiltros<T>(
  row: T,
  filtros: Record<DimKey, string>,
  valoresFn: (row: T) => Record<DimKey, string>,
  exclude?: DimKey,
): boolean {
  const valores = valoresFn(row);
  return (Object.keys(filtros) as DimKey[]).every(
    (key) => key === exclude || !filtros[key] || filtros[key] === valores[key],
  );
}

// Si estamos abriendo un HTML exportado (ver src/utils/exportarHtml.ts), esta
// variable global viene con los datos completos embebidos y no hay backend
// al que pedirle nada.
const datosExportados = typeof window !== "undefined" ? window.__PDA_EXPORT__ : undefined;

interface SobretiempoDashboardPageProps {
  userRole?: UserRole;
}

export function SobretiempoDashboardPage({ userRole }: SobretiempoDashboardPageProps = {}) {
  const [resumen, setResumen] = useState<Resumen[]>([]);
  // Igual que resumen, pero sin el filtro de Mes: los paneles de tendencia
  // anual (Resumen Ejecutivo, Control Mensual) necesitan los 12 meses para
  // poder sumar el presupuesto anual y armar la curva mensual, pero deben
  // seguir respetando el resto de los filtros (sociedad, gerencia, etc.).
  const [resumenAnual, setResumenAnual] = useState<Resumen[]>([]);
  const [detalle, setDetalle] = useState<Detalle[]>([]);
  const [opciones, setOpciones] = useState<Resumen[]>(datosExportados?.resumenCompleto ?? []);
  const [detalleCompleto] = useState<Detalle[]>(datosExportados?.detalleCompleto ?? []);

  const [mesFiltro, setMesFiltro] = useState("");
  const [sociedadFiltro, setSociedadFiltro] = useState("");
  const [gerenciaFiltro, setGerenciaFiltro] = useState("");
  const [subgerenciaFiltro, setSubgerenciaFiltro] = useState("");
  const [unidadFiltro, setUnidadFiltro] = useState("");
  const [cecoFiltro, setCecoFiltro] = useState("");
  const [cuentaFiltro, setCuentaFiltro] = useState("");

  const [dimensionSaldo, setDimensionSaldo] = useState<DimensionSaldo>("sociedad");

  const [ordenColumna, setOrdenColumna] = useState("real");
  const [ordenAsc, setOrdenAsc] = useState(false);

  const [ordenColumnaTx, setOrdenColumnaTx] = useState("importe");
  const [ordenAscTx, setOrdenAscTx] = useState(false);

  const [loading, setLoading] = useState(!datosExportados);
  const [error, setError] = useState<string | null>(null);
  const [exportando, setExportando] = useState(false);
  const [errorExportar, setErrorExportar] = useState<string | null>(null);

  const [actualizando, setActualizando] = useState(false);
  const [errorActualizar, setErrorActualizar] = useState<string | null>(null);
  const [resultadoActualizar, setResultadoActualizar] = useState<ResultadoActualizacion | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const inputArchivoRef = useRef<HTMLInputElement>(null);

  // Opciones de los filtros: se cargan una sola vez, sin filtrar, para que
  // las listas desplegables no se vacien a medida que se van aplicando filtros.
  // En un HTML exportado ya vienen embebidas, no hace falta pedirlas.
  useEffect(() => {
    if (datosExportados) return;
    getResumen({}).then(setOpciones).catch(() => undefined);
  }, [refreshKey]);

  useEffect(() => {
    if (datosExportados) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const filtrosOrg = {
      ...(sociedadFiltro && { sociedad: sociedadFiltro }),
      ...(gerenciaFiltro && { gerencia: gerenciaFiltro }),
      ...(subgerenciaFiltro && { subgerencia: subgerenciaFiltro }),
      ...(unidadFiltro && { unidad: unidadFiltro }),
      ...(cecoFiltro && { ceco: cecoFiltro }),
      ...(cuentaFiltro && { cuenta: Number(cuentaFiltro) }),
    };
    const filtros = {
      ...filtrosOrg,
      ...(mesFiltro && { mes: MESES_ORDEN.indexOf(mesFiltro) + 1 }),
    };

    Promise.all([getResumen(filtros), getDetalle(filtros), getResumen(filtrosOrg)])
      .then(([r, d, rAnual]) => {
        if (cancelled) return;
        setResumen(r);
        setDetalle(d);
        setResumenAnual(rAnual);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "No se pudo cargar el dashboard");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro, cuentaFiltro, refreshKey]);

  // Equivalente al fetch de arriba, pero filtrando 100% en el navegador
  // contra los datasets completos embebidos — es lo que corre cuando el
  // archivo exportado se abre sin backend.
  useEffect(() => {
    if (!datosExportados) return;
    const filtros: Record<DimKey, string> = {
      mes: mesFiltro,
      sociedad: sociedadFiltro,
      gerencia: gerenciaFiltro,
      subgerencia: subgerenciaFiltro,
      unidad: unidadFiltro,
      ceco: cecoFiltro,
      cuenta: cuentaFiltro,
    };
    const filtrosOrg: Record<DimKey, string> = { ...filtros, mes: "" };
    setResumen(opciones.filter((r) => coincideConFiltros(r, filtros, extraerValoresResumen)));
    setDetalle(detalleCompleto.filter((d) => coincideConFiltros(d, filtros, extraerValoresDetalle)));
    setResumenAnual(opciones.filter((r) => coincideConFiltros(r, filtrosOrg, extraerValoresResumen)));
  }, [opciones, detalleCompleto, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro, cuentaFiltro]);

  const filtrosActivos: Record<DimKey, string> = {
    mes: mesFiltro,
    sociedad: sociedadFiltro,
    gerencia: gerenciaFiltro,
    subgerencia: subgerenciaFiltro,
    unidad: unidadFiltro,
    ceco: cecoFiltro,
    cuenta: cuentaFiltro,
  };

  const mesesDisponibles = useMemo(() => {
    const filas = opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "mes"));
    const presentes = new Set(filas.map((r) => r.Mes_Nombre));
    return MESES_ORDEN.filter((m) => presentes.has(m));
  }, [opciones, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro, cuentaFiltro]);

  const sociedadesDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "sociedad")).map((r) => r.Sociedad)),
    [opciones, mesFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro, cuentaFiltro],
  );

  const gerenciasDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "gerencia")).map((r) => r.Gerencia)),
    [opciones, mesFiltro, sociedadFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro, cuentaFiltro],
  );

  const subgerenciasDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "subgerencia")).map((r) => r.Subgerencia)),
    [opciones, mesFiltro, sociedadFiltro, gerenciaFiltro, unidadFiltro, cecoFiltro, cuentaFiltro],
  );

  const unidadesDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "unidad")).map((r) => r.Unidad_Organizativa)),
    [opciones, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, cecoFiltro, cuentaFiltro],
  );

  const cecosDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "ceco")).map((r) => r.Ceco)),
    [opciones, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cuentaFiltro],
  );

  const cuentasDisponibles = useMemo(
    () =>
      uniqueSorted(
        opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "cuenta")).map((r) => String(r.Cuenta_Contable)),
      ),
    [opciones, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro],
  );

  // Si al acotar un filtro la seleccion vigente de otro deja de tener sentido
  // (ej. eligo Sociedad y la Gerencia que tenia puesta no pertenece a esa
  // Sociedad), se limpia sola en vez de mandar al backend un cruce vacio.
  useEffect(() => {
    if (mesFiltro && !mesesDisponibles.includes(mesFiltro)) setMesFiltro("");
  }, [mesesDisponibles, mesFiltro]);
  useEffect(() => {
    if (sociedadFiltro && !sociedadesDisponibles.includes(sociedadFiltro)) setSociedadFiltro("");
  }, [sociedadesDisponibles, sociedadFiltro]);
  useEffect(() => {
    if (gerenciaFiltro && !gerenciasDisponibles.includes(gerenciaFiltro)) setGerenciaFiltro("");
  }, [gerenciasDisponibles, gerenciaFiltro]);
  useEffect(() => {
    if (subgerenciaFiltro && !subgerenciasDisponibles.includes(subgerenciaFiltro)) setSubgerenciaFiltro("");
  }, [subgerenciasDisponibles, subgerenciaFiltro]);
  useEffect(() => {
    if (unidadFiltro && !unidadesDisponibles.includes(unidadFiltro)) setUnidadFiltro("");
  }, [unidadesDisponibles, unidadFiltro]);
  useEffect(() => {
    if (cecoFiltro && !cecosDisponibles.includes(cecoFiltro)) setCecoFiltro("");
  }, [cecosDisponibles, cecoFiltro]);
  useEffect(() => {
    if (cuentaFiltro && !cuentasDisponibles.includes(cuentaFiltro)) setCuentaFiltro("");
  }, [cuentasDisponibles, cuentaFiltro]);

  const ultimoMesCerrado = useMemo(() => {
    const cerrados = resumenAnual.filter((r) => r.Mes_Cerrado).map((r) => r.Mes_Num);
    return cerrados.length ? Math.max(...cerrados) : 0;
  }, [resumenAnual]);

  // Igual que hacia resumen_gerencia: el avance vs. presupuesto SOLO
  // considera Ceco+Cuenta con presupuesto asignado (el gasto cargado a un
  // PEP/proyecto sin Ceco queda fuera de este calculo, aunque sigue
  // apareciendo en el detalle transaccional de "¿En que se gasto?").
  const resumenAnualPresupuestado = useMemo(
    () => resumenAnual.filter((r) => r.Con_Presupuesto_Asignado),
    [resumenAnual],
  );

  const saldoPorDimension = useMemo(() => {
    const dimension = DIMENSIONES_SALDO.find((d) => d.value === dimensionSaldo) ?? DIMENSIONES_SALDO[0];
    return agregarSaldoPorDimension(resumenAnualPresupuestado, dimension.keyFn, ultimoMesCerrado);
  }, [resumenAnualPresupuestado, ultimoMesCerrado, dimensionSaldo]);

  const presupuestoAnualTotal = useMemo(
    () => sum(resumenAnualPresupuestado.map((r) => r.Presupuesto)),
    [resumenAnualPresupuestado],
  );

  const mesesOrdenados = useMemo(() => {
    const porMes = new Map<number, { nombre: string; real: number; realMes: number }>();
    for (const r of resumenAnualPresupuestado) {
      const actual = porMes.get(r.Mes_Num) ?? { nombre: r.Mes_Nombre, real: 0, realMes: 0 };
      actual.real += r.Real_Acumulado;
      actual.realMes += r.Importe_Real;
      porMes.set(r.Mes_Num, actual);
    }
    return Array.from(porMes.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([num, v]) => [num, { ...v, presupuesto: presupuestoAnualTotal }] as const);
  }, [resumenAnualPresupuestado, presupuestoAnualTotal]);

  const detalleMesActual = useMemo(() => {
    const cerrados = resumen.filter((r) => r.Mes_Cerrado).map((r) => r.Mes_Num);
    const ultimo = cerrados.length ? Math.max(...cerrados) : 0;
    return resumen.filter((r) => r.Mes_Num === ultimo);
  }, [resumen]);

  const detalleOrdenado = useMemo(
    () => ordenarFilas(detalleMesActual, COLUMNAS_DETALLE, ordenColumna, ordenAsc),
    [detalleMesActual, ordenColumna, ordenAsc],
  );

  function ordenarPor(id: string) {
    if (ordenColumna === id) {
      setOrdenAsc((prev) => !prev);
    } else {
      setOrdenColumna(id);
      setOrdenAsc(false);
    }
  }

  const transaccionesOrdenadas = useMemo(
    () => ordenarFilas(detalle, COLUMNAS_TRANSACCIONES, ordenColumnaTx, ordenAscTx),
    [detalle, ordenColumnaTx, ordenAscTx],
  );

  function ordenarTransaccionesPor(id: string) {
    if (ordenColumnaTx === id) {
      setOrdenAscTx((prev) => !prev);
    } else {
      setOrdenColumnaTx(id);
      setOrdenAscTx(false);
    }
  }

  const gastoPorConcepto = useMemo(() => {
    const map = groupSum(detalle, (d) => d.Concepto, (d) => d.Importe);
    return Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
  }, [detalle]);

  const conVsSinPresupuesto = useMemo(() => {
    const con = sum(detalle.filter((d) => d.Con_Presupuesto_Asignado).map((d) => d.Importe));
    const sin = sum(detalle.filter((d) => !d.Con_Presupuesto_Asignado).map((d) => d.Importe));
    return { con, sin };
  }, [detalle]);

  async function manejarExportar() {
    setExportando(true);
    setErrorExportar(null);
    try {
      await exportarDashboardHtml(opciones);
    } catch (err) {
      setErrorExportar(err instanceof Error ? err.message : "No se pudo exportar el reporte");
    } finally {
      setExportando(false);
    }
  }

  async function manejarSeleccionArchivo(e: ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    e.target.value = ""; // permite volver a elegir el mismo archivo si hace falta reintentar
    if (!archivo) return;

    setActualizando(true);
    setErrorActualizar(null);
    setResultadoActualizar(null);
    try {
      const resultado = await actualizarDatos(archivo);
      setResultadoActualizar(resultado);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setErrorActualizar(err instanceof ApiError ? err.message : "No se pudo actualizar los datos");
    } finally {
      setActualizando(false);
    }
  }

  if (loading) {
    return <p>Cargando...</p>;
  }

  if (error) {
    return <p className="sobretiempo__error">{error}</p>;
  }

  return (
    <div className="sobretiempo">
      {datosExportados && (
        <div className="sobretiempo__export-banner">Reporte exportado el {datosExportados.generadoEl}.</div>
      )}

      <div className="sobretiempo__header">
        <div>
          <h1>Sobretiempo</h1>
          <p className="sobretiempo__subtitle">Control mensual de horas extra vs. presupuesto</p>
          {!datosExportados && (
            <div className="sobretiempo__export-action">
              <button type="button" className="btn" onClick={manejarExportar} disabled={exportando}>
                {exportando ? "Generando..." : "Descargar reporte (HTML)"}
              </button>
              {userRole === "administrador" && (
                <button
                  type="button"
                  className="btn sobretiempo__btn-secundario"
                  onClick={() => inputArchivoRef.current?.click()}
                  disabled={actualizando}
                >
                  {actualizando ? "Actualizando..." : "Actualizar datos (Excel)"}
                </button>
              )}
              <input
                ref={inputArchivoRef}
                type="file"
                accept=".xlsx"
                className="sobretiempo__input-archivo"
                onChange={manejarSeleccionArchivo}
              />
              {errorExportar && <p className="sobretiempo__error sobretiempo__export-error">{errorExportar}</p>}
              {errorActualizar && <p className="sobretiempo__error sobretiempo__export-error">{errorActualizar}</p>}
              {resultadoActualizar && (
                <p className="sobretiempo__export-ok">
                  Datos actualizados: {resultadoActualizar.detalle.toLocaleString("es-CL")} filas de detalle,{" "}
                  {resultadoActualizar.resumen.toLocaleString("es-CL")} de resumen.
                  {resultadoActualizar.backup && " Se guardó un respaldo de la base anterior."}
                </p>
              )}
            </div>
          )}
        </div>
        <div className="sobretiempo__filters">
          <SearchableSelect label="Mes" value={mesFiltro} options={mesesDisponibles} onChange={setMesFiltro} />
          <SearchableSelect label="Sociedad" value={sociedadFiltro} options={sociedadesDisponibles} onChange={setSociedadFiltro} />
          <SearchableSelect label="Gerencia" value={gerenciaFiltro} options={gerenciasDisponibles} onChange={setGerenciaFiltro} />
          <SearchableSelect label="Subgerencia" value={subgerenciaFiltro} options={subgerenciasDisponibles} onChange={setSubgerenciaFiltro} />
          <SearchableSelect label="Unidad" value={unidadFiltro} options={unidadesDisponibles} onChange={setUnidadFiltro} />
          <SearchableSelect label="Centro Costo" value={cecoFiltro} options={cecosDisponibles} placeholder="Todos" onChange={setCecoFiltro} />
          <SearchableSelect label="Cuenta" value={cuentaFiltro} options={cuentasDisponibles} onChange={setCuentaFiltro} />
        </div>
      </div>

      <section>
        <h2>Control Mensual</h2>
        <div className="sobretiempo__panel-grid">
          <div className="card">
            <h3>Real acumulado vs. Presupuesto anual</h3>
            <div className="sobretiempo__chart">
              <Line
                data={{
                  labels: mesesOrdenados.map(([, v]) => v.nombre),
                  datasets: [
                    {
                      label: "Real acumulado",
                      data: mesesOrdenados.map(([, v]) => v.real),
                      borderColor: CHART_COLORS.red,
                      backgroundColor: CHART_COLORS.red,
                      tension: 0.3,
                    },
                    {
                      label: "Presupuesto anual",
                      data: mesesOrdenados.map(([, v]) => v.presupuesto),
                      borderColor: CHART_COLORS.navy,
                      backgroundColor: CHART_COLORS.navy,
                      borderDash: [6, 4],
                      tension: 0,
                    },
                  ],
                }}
                options={{ responsive: true, maintainAspectRatio: false }}
              />
            </div>
          </div>
          <div className="card">
            <h3>Gasto real por mes</h3>
            <div className="sobretiempo__chart">
              <Bar
                data={{
                  labels: mesesOrdenados.map(([, v]) => v.nombre),
                  datasets: [
                    {
                      label: "Gasto real",
                      data: mesesOrdenados.map(([, v]) => v.realMes),
                      backgroundColor: CHART_COLORS.red,
                      borderRadius: 6,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  layout: { padding: { top: 22 } },
                  plugins: {
                    legend: { display: false },
                    datalabels: {
                      anchor: "end",
                      align: "top",
                      color: CHART_COLORS.navy,
                      font: { size: 10, weight: "bold" },
                      formatter: (v: number) => formatCompactCurrency(v),
                    },
                  },
                }}
                plugins={[ChartDataLabels]}
              />
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2>¿En qué se gastó?</h2>
        <div className="sobretiempo__panel-grid">
          <div className="card">
            <h3>Gasto por concepto</h3>
            <div className="sobretiempo__chart">
              <Bar
                data={{
                  labels: gastoPorConcepto.map(([c]) => c),
                  datasets: [
                    {
                      label: "Importe",
                      data: gastoPorConcepto.map(([, v]) => v),
                      backgroundColor: CHART_COLORS.navy,
                      borderRadius: 6,
                    },
                  ],
                }}
                options={{
                  indexAxis: "y",
                  responsive: true,
                  maintainAspectRatio: false,
                  layout: { padding: { right: 48 } },
                  plugins: {
                    legend: { display: false },
                    datalabels: {
                      anchor: "end",
                      align: "end",
                      clamp: true,
                      color: CHART_COLORS.navy,
                      font: { size: 10, weight: "bold" },
                      formatter: (v: number) => formatCompactCurrency(v),
                    },
                  },
                }}
                plugins={[ChartDataLabels]}
              />
            </div>
          </div>
          <div className="card">
            <h3>Con presupuesto vs. sin presupuesto</h3>
            <div className="sobretiempo__chart sobretiempo__chart--donut">
              <Doughnut
                data={{
                  labels: ["Con presupuesto", "Sin presupuesto"],
                  datasets: [
                    {
                      data: [conVsSinPresupuesto.con, conVsSinPresupuesto.sin],
                      backgroundColor: [CHART_COLORS.success, CHART_COLORS.red],
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    datalabels: {
                      color: "#fff",
                      font: { weight: "bold", size: 13 },
                      formatter: (value: number, ctx: Context) => {
                        const data = (ctx.chart.data.datasets[0].data as number[]) ?? [];
                        const total = data.reduce((a, b) => a + b, 0);
                        return total ? `${((value / total) * 100).toFixed(1)}%` : "";
                      },
                    },
                  },
                }}
                plugins={[ChartDataLabels]}
              />
            </div>
          </div>
        </div>

        <div className="card sobretiempo__table-card">
          <h3>Ranking de Importe</h3>
          <div className="sobretiempo__table-wrap sobretiempo__table-wrap--scroll sobretiempo__table-wrap--rows10">
            <table>
              <thead>
                <tr>
                  {COLUMNAS_TRANSACCIONES.map((c) => (
                    <th key={c.id}>
                      <button
                        type="button"
                        className="sobretiempo__th-sort"
                        onClick={() => ordenarTransaccionesPor(c.id)}
                      >
                        {c.label}
                        <span className="sobretiempo__sort-arrow">
                          {ordenColumnaTx === c.id ? (ordenAscTx ? "▲" : "▼") : ""}
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transaccionesOrdenadas.map((d, i) => (
                  <tr key={i}>
                    {COLUMNAS_TRANSACCIONES.map((c) => (
                      <td key={c.id}>{c.render(d)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section>
        <h2>Resumen Ejecutivo</h2>
        <div className="card">
          <h3>Saldo disponible</h3>
          <div className="sobretiempo__dim-toggle">
            {DIMENSIONES_SALDO.map((d) => (
              <label key={d.value} className="sobretiempo__dim-option">
                <input
                  type="radio"
                  name="dimension-saldo"
                  checked={dimensionSaldo === d.value}
                  onChange={() => setDimensionSaldo(d.value)}
                />
                <span className="sobretiempo__dim-circle" />
                {d.label}
              </label>
            ))}
          </div>
          <div className="sobretiempo__chart-scroll">
            <div
              className="sobretiempo__chart"
              style={{ height: Math.max(saldoPorDimension.length * 26, 340) }}
            >
              <Bar
                data={{
                  labels: saldoPorDimension.map(([k]) => k),
                  datasets: [
                    {
                      label: "Saldo disponible",
                      data: saldoPorDimension.map(([, v]) => v),
                      backgroundColor: saldoPorDimension.map(([, v]) =>
                        v >= 0 ? CHART_COLORS.success : CHART_COLORS.red,
                      ),
                      borderRadius: 6,
                    },
                  ],
                }}
                options={{
                  indexAxis: "y",
                  responsive: true,
                  maintainAspectRatio: false,
                  layout: { padding: { left: 48, right: 48 } },
                  plugins: {
                    legend: { display: false },
                    datalabels: {
                      anchor: "end",
                      align: "end",
                      clamp: true,
                      color: CHART_COLORS.navy,
                      font: { size: 10, weight: "bold" },
                      formatter: (v: number) => formatCompactCurrency(v),
                    },
                  },
                }}
                plugins={[ChartDataLabels]}
              />
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2>Detalle</h2>
        <div className="card">
          <div className="sobretiempo__table-wrap sobretiempo__table-wrap--scroll sobretiempo__table-wrap--rows15">
            <table className="sobretiempo__table--detalle">
              <thead>
                <tr>
                  {COLUMNAS_DETALLE.map((c) => (
                    <th key={c.id}>
                      <button
                        type="button"
                        className="sobretiempo__th-sort"
                        onClick={() => ordenarPor(c.id)}
                      >
                        {c.label}
                        <span className="sobretiempo__sort-arrow">
                          {ordenColumna === c.id ? (ordenAsc ? "▲" : "▼") : ""}
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {detalleOrdenado.map((r, i) => (
                  <tr key={i}>
                    {COLUMNAS_DETALLE.map((c) => (
                      <td key={c.id}>{c.render(r)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
