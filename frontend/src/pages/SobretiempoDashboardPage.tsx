import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { Bar, Line } from "react-chartjs-2";
import ChartDataLabels from "chartjs-plugin-datalabels";
import { CHART_COLORS } from "../charts/registerCharts";
import { SearchableSelect } from "../components/SearchableSelect";
import { SearchableMultiSelect } from "../components/SearchableMultiSelect";
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

// Mismos codigos que SOCIEDAD_MAP en backend/dashboards/sobretiempo/normalizar.py,
// invertido — para mostrar la sigla en vez del nombre completo en tablas angostas.
const SOCIEDAD_SIGLA: Record<string, string> = {
  "Chilquinta Energía S.A.": "CC",
  "Chilquinta Distribución S": "CE",
  "Chilquinta Servicios S.A.": "CS",
  "Chilquinta Transmisión S.": "CX",
  "Energ. de Casablanca S.A.": "CA",
  "C. Eléc. del Litoral S.A.": "LT",
  "Luzlinares S.A.": "LN",
  "Luzparral S.A.": "LP",
};

function siglaSociedad(nombre: string): string {
  return SOCIEDAD_SIGLA[nombre] ?? nombre;
}

const MESES_ORDEN = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];


const COLUMNAS_DETALLE: Columna<Resumen>[] = [
  { id: "sociedad", label: "Sociedad", valor: (r) => r.Sociedad, render: (r) => siglaSociedad(r.Sociedad) },
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

const UMBRAL_ADVERTENCIA = 0.5;
const UMBRAL_CRITICO = 0.7;

function nivelAlerta(pct: number): "critico" | "advertencia" {
  return pct >= UMBRAL_CRITICO ? "critico" : "advertencia";
}

// Ritmo de ejecucion = (Real acumulado / Presupuesto ANUAL fijo) dividido el
// % del año ya transcurrido (Mes_Num / 12). A diferencia de "% Gastado"
// (que compara contra el presupuesto acumulado A LA FECHA, y por eso da mas
// alto a medida que avanza el año sin importar el ritmo real), este numero
// es 1.0 si vas exactamente al ritmo esperado, sin importar el mes: no es lo
// mismo alertar en enero que en diciembre. El mismo numero, multiplicado por
// el presupuesto anual, da la proyeccion de gasto a fin de año si se sigue
// al mismo ritmo. Son dos indicadores distintos y se muestran juntos en la
// misma tabla para poder compararlos cuenta por cuenta.
const RITMO_ADVERTENCIA = 1.0;
const RITMO_CRITICO = 1.3;

function nivelRitmo(ritmo: number): "critico" | "advertencia" {
  return ritmo >= RITMO_CRITICO ? "critico" : "advertencia";
}

// Nivel de la fila = el peor de los dos indicadores (si cualquiera de los
// dos esta en critico, la fila se pinta critico).
function nivelCombinado(pct: number, ritmo: number): "critico" | "advertencia" {
  return pct >= UMBRAL_CRITICO || ritmo >= RITMO_CRITICO ? "critico" : "advertencia";
}

interface CuentaConRitmo extends Resumen {
  presupuestoAnual: number;
  ritmo: number;
  proyeccionAnual: number;
  excedenteProyectado: number;
}

const COLUMNAS_ALERTA: Columna<CuentaConRitmo>[] = [
  {
    id: "pct",
    label: "% Gastado",
    valor: (r) => r.Pct_Ejecucion_Acumulado ?? 0,
    render: (r) => {
      const pct = r.Pct_Ejecucion_Acumulado ?? 0;
      return (
        <span className={`sobretiempo__badge-alerta sobretiempo__badge-alerta--${nivelAlerta(pct)}`}>
          {(pct * 100).toFixed(1)}%
        </span>
      );
    },
  },
  {
    id: "ritmo",
    label: "Ritmo de gasto",
    valor: (r) => r.ritmo,
    render: (r) => (
      <span className={`sobretiempo__badge-alerta sobretiempo__badge-alerta--${nivelRitmo(r.ritmo)}`}>
        {r.ritmo.toFixed(2)}x
      </span>
    ),
  },
  { id: "sociedad", label: "Sociedad", valor: (r) => r.Sociedad, render: (r) => siglaSociedad(r.Sociedad) },
  { id: "gerencia", label: "Gerencia", valor: (r) => r.Gerencia, render: (r) => r.Gerencia },
  { id: "subgerencia", label: "Subgerencia", valor: (r) => r.Subgerencia, render: (r) => r.Subgerencia },
  { id: "unidad", label: "Unidad", valor: (r) => r.Unidad_Organizativa, render: (r) => r.Unidad_Organizativa },
  {
    id: "presupuesto_anual",
    label: "Ppto. anual",
    valor: (r) => r.presupuestoAnual,
    render: (r) => formatCurrency(r.presupuestoAnual),
  },
  {
    id: "real",
    label: "Gastado",
    valor: (r) => r.Real_Acumulado,
    render: (r) => formatCurrency(r.Real_Acumulado),
  },
  {
    id: "saldo",
    label: "Saldo",
    valor: (r) => r.Saldo_Acumulado,
    render: (r) => (
      <span className={r.Saldo_Acumulado < 0 ? "negativo" : "positivo"}>{formatCurrency(r.Saldo_Acumulado)}</span>
    ),
  },
  {
    id: "proyeccion",
    label: "Proyección",
    valor: (r) => r.proyeccionAnual,
    render: (r) => formatCurrency(r.proyeccionAnual),
  },
  {
    id: "excedente",
    label: "Excedente",
    valor: (r) => r.excedenteProyectado,
    render: (r) => (
      <span className={r.excedenteProyectado > 0 ? "negativo" : "positivo"}>
        {formatCurrency(r.excedenteProyectado)}
      </span>
    ),
  },
];

// "Ranking de Importe": una fila por persona (no por transacción — ver
// CLAUDE.md "Patron de dashboards", sobretiempo_detalle trae un registro
// por persona/Concepto/mes, así que sin agregar una misma persona aparecía
// muchas veces, hasta repetida en el mismo Concepto). Se agrega por
// Cod_SAP sumando Importe, con una columna de desglose por cada Concepto
// (ademas del Total) para no perder el detalle que antes daba la columna
// "Concepto" de una fila por transacción.
const CONCEPTOS_RANKING = [
  "Hora Extra",
  "Turnos",
  "Citación",
  "Rot Horas Extra/Turnos",
  "Bono Disponibilidad/Interluz/Alerta",
];

interface PersonaImporte {
  Cod_SAP: number;
  Nombre_Personal: string;
  Cargo: string;
  Gerencia: string;
  PorConcepto: Record<string, number>;
  Horas: number;
  Total: number;
}

function agregarPorPersona(rows: Detalle[]): PersonaImporte[] {
  const map = new Map<number, PersonaImporte>();
  for (const d of rows) {
    let persona = map.get(d.Cod_SAP);
    if (!persona) {
      persona = {
        Cod_SAP: d.Cod_SAP,
        Nombre_Personal: d.Nombre_Personal,
        Cargo: d.Cargo,
        Gerencia: d.Gerencia,
        PorConcepto: {},
        Horas: 0,
        Total: 0,
      };
      map.set(d.Cod_SAP, persona);
    }
    persona.PorConcepto[d.Concepto] = (persona.PorConcepto[d.Concepto] ?? 0) + d.Importe;
    persona.Horas += d.Cantidad_Horas;
    persona.Total += d.Importe;
  }
  return Array.from(map.values());
}

// Labels acortados para las columnas de Concepto con nombres largos pero
// pocas personas (ensanchaban la tabla sin aportar densidad de datos) — el
// nombre completo queda como tooltip (title) en el header, ver `titulo`.
const LABEL_CONCEPTO_CORTO: Record<string, string> = {
  "Rot Horas Extra/Turnos": "Rot HE/Turnos",
  "Bono Disponibilidad/Interluz/Alerta": "Bono Disp.",
};

// Arma las columnas del ranking a partir de los Concepto que SI tienen
// datos en el alcance de filtros actual — un Concepto sin ninguna persona
// (columna entera en $0) se oculta en vez de mostrarse vacía, a pedido del
// usuario. `conceptosVisibles` ya viene filtrado (ver useMemo en el
// componente), acá solo arma las definiciones de columna.
function construirColumnasRanking(conceptosVisibles: string[]): Columna<PersonaImporte>[] {
  return [
    { id: "nombre", label: "Nombre", valor: (d) => d.Nombre_Personal, render: (d) => d.Nombre_Personal },
    { id: "cargo", label: "Cargo", valor: (d) => d.Cargo, render: (d) => d.Cargo },
    { id: "gerencia", label: "Gerencia", valor: (d) => d.Gerencia, render: (d) => d.Gerencia },
    { id: "horas", label: "Horas", valor: (d) => d.Horas, render: (d) => d.Horas.toFixed(1) },
    ...conceptosVisibles.map((concepto) => ({
      id: `concepto-${concepto}`,
      label: LABEL_CONCEPTO_CORTO[concepto] ?? concepto,
      titulo: concepto,
      valor: (d: PersonaImporte) => d.PorConcepto[concepto] ?? 0,
      render: (d: PersonaImporte) => formatCurrency(d.PorConcepto[concepto] ?? 0),
    })),
    { id: "total", label: "Total", valor: (d) => d.Total, render: (d) => formatCurrency(d.Total) },
  ];
}

type DimKey = "mes" | "sociedad" | "gerencia" | "subgerencia" | "unidad" | "ceco";

function extraerValoresResumen(row: Resumen): Record<DimKey, string> {
  return {
    mes: row.Mes_Nombre,
    sociedad: row.Sociedad,
    gerencia: row.Gerencia,
    subgerencia: row.Subgerencia,
    unidad: row.Unidad_Organizativa,
    ceco: row.Ceco,
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
  };
}

// Ceco admite seleccion multiple (array); el resto de estos filtros sigue
// siendo un solo valor (string). Concepto (Horas Extras, Turno, etc.) es
// otro multi-select aparte, ver conceptoFiltro — no es parte de este set
// porque solo existe en el detalle transaccional, no en "resumen".
type FiltroValor = string | string[];

function coincideValor(filtroValor: FiltroValor, valorFila: string): boolean {
  if (Array.isArray(filtroValor)) {
    return filtroValor.length === 0 || filtroValor.includes(valorFila);
  }
  return !filtroValor || filtroValor === valorFila;
}

// Compara una fila contra los filtros activos. Si se pasa "exclude", esa
// dimension no se evalua (sirve para calcular las opciones de UN filtro sin
// que se autoelimine sus propias opciones). Sin "exclude", filtra por TODAS
// las dimensiones activas — es lo que se usa para armar los datos reales,
// tanto pidiendolos al backend como (en un HTML exportado) filtrando en el
// propio navegador contra el dataset completo embebido.
function coincideConFiltros<T>(
  row: T,
  filtros: Record<DimKey, FiltroValor>,
  valoresFn: (row: T) => Record<DimKey, string>,
  exclude?: DimKey,
): boolean {
  const valores = valoresFn(row);
  return (Object.keys(filtros) as DimKey[]).every(
    (key) => key === exclude || coincideValor(filtros[key], valores[key]),
  );
}

// Si estamos abriendo un HTML exportado (ver src/utils/exportarHtml.ts), esta
// variable global viene con los datos completos embebidos y no hay backend
// al que pedirle nada.
const datosExportados = typeof window !== "undefined" ? window.__PDA_EXPORT__ : undefined;

interface SobretiempoDashboardPageProps {
  userRole?: UserRole;
  userName?: string;
}

export function SobretiempoDashboardPage({ userRole, userName }: SobretiempoDashboardPageProps = {}) {
  const [resumen, setResumen] = useState<Resumen[]>([]);
  // Igual que resumen, pero sin el filtro de Mes: los paneles de tendencia
  // anual (Resumen Ejecutivo, Control Mensual) necesitan los 12 meses para
  // poder sumar el presupuesto anual y armar la curva mensual, pero deben
  // seguir respetando el resto de los filtros (sociedad, gerencia, etc.).
  const [resumenAnual, setResumenAnual] = useState<Resumen[]>([]);
  const [detalle, setDetalle] = useState<Detalle[]>([]);
  const [opciones, setOpciones] = useState<Resumen[]>(datosExportados?.resumenCompleto ?? []);
  // Fuente "sin filtrar" del detalle transaccional, usada para calcular las
  // opciones disponibles de Concepto (cascada) — mismo rol que "opciones"
  // cumple para el resto de los filtros, pero de la tabla Detalle.
  const [detalleCompleto, setDetalleCompleto] = useState<Detalle[]>(datosExportados?.detalleCompleto ?? []);

  const [mesFiltro, setMesFiltro] = useState("");
  const [sociedadFiltro, setSociedadFiltro] = useState<string[]>([]);
  const [gerenciaFiltro, setGerenciaFiltro] = useState<string[]>([]);
  const [subgerenciaFiltro, setSubgerenciaFiltro] = useState<string[]>([]);
  const [unidadFiltro, setUnidadFiltro] = useState<string[]>([]);
  const [cecoFiltro, setCecoFiltro] = useState<string[]>([]);
  // Concepto (Horas Extras, Turno, etc.) solo existe en el detalle
  // transaccional — filtra "¿En que se gasto?"/Ranking de Importe/Detalle
  // transaccional, pero no los paneles que vienen de "resumen"
  // (Control Mensual, Saldo disponible, Alerta, tabla Detalle).
  const [conceptoFiltro, setConceptoFiltro] = useState<string[]>([]);

  const [ordenColumna, setOrdenColumna] = useState("real");
  const [ordenAsc, setOrdenAsc] = useState(false);

  const [ordenColumnaTx, setOrdenColumnaTx] = useState("total");
  const [ordenAscTx, setOrdenAscTx] = useState(false);

  const [ordenColumnaAlerta, setOrdenColumnaAlerta] = useState("pct");
  const [ordenAscAlerta, setOrdenAscAlerta] = useState(false);

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
    getDetalle({}).then(setDetalleCompleto).catch(() => undefined);
  }, [refreshKey]);

  useEffect(() => {
    if (datosExportados) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const filtrosOrg = {
      ...(sociedadFiltro.length > 0 && { sociedad: sociedadFiltro }),
      ...(gerenciaFiltro.length > 0 && { gerencia: gerenciaFiltro }),
      ...(subgerenciaFiltro.length > 0 && { subgerencia: subgerenciaFiltro }),
      ...(unidadFiltro.length > 0 && { unidad: unidadFiltro }),
      ...(cecoFiltro.length > 0 && { ceco: cecoFiltro }),
    };
    const filtros = {
      ...filtrosOrg,
      ...(mesFiltro && { mes: MESES_ORDEN.indexOf(mesFiltro) + 1 }),
    };
    // Concepto solo aplica al detalle transaccional — "resumen" no tiene esa
    // columna (esta pre-agregado por Ceco+Cuenta+Mes).
    const filtrosDetalle = {
      ...filtros,
      ...(conceptoFiltro.length > 0 && { concepto: conceptoFiltro }),
    };

    Promise.all([getResumen(filtros), getDetalle(filtrosDetalle), getResumen(filtrosOrg)])
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
  }, [mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro, conceptoFiltro, refreshKey]);

  // Equivalente al fetch de arriba, pero filtrando 100% en el navegador
  // contra los datasets completos embebidos — es lo que corre cuando el
  // archivo exportado se abre sin backend.
  useEffect(() => {
    if (!datosExportados) return;
    const filtros: Record<DimKey, FiltroValor> = {
      mes: mesFiltro,
      sociedad: sociedadFiltro,
      gerencia: gerenciaFiltro,
      subgerencia: subgerenciaFiltro,
      unidad: unidadFiltro,
      ceco: cecoFiltro,
    };
    const filtrosOrg: Record<DimKey, FiltroValor> = { ...filtros, mes: "" };
    setResumen(opciones.filter((r) => coincideConFiltros(r, filtros, extraerValoresResumen)));
    setDetalle(
      detalleCompleto.filter(
        (d) =>
          coincideConFiltros(d, filtros, extraerValoresDetalle) &&
          coincideValor(conceptoFiltro, d.Concepto),
      ),
    );
    setResumenAnual(opciones.filter((r) => coincideConFiltros(r, filtrosOrg, extraerValoresResumen)));
  }, [opciones, detalleCompleto, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro, conceptoFiltro]);

  const filtrosActivos: Record<DimKey, FiltroValor> = {
    mes: mesFiltro,
    sociedad: sociedadFiltro,
    gerencia: gerenciaFiltro,
    subgerencia: subgerenciaFiltro,
    unidad: unidadFiltro,
    ceco: cecoFiltro,
  };

  const mesesDisponibles = useMemo(() => {
    const filas = opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "mes"));
    const presentes = new Set(filas.map((r) => r.Mes_Nombre));
    return MESES_ORDEN.filter((m) => presentes.has(m));
  }, [opciones, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro]);

  const sociedadesDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "sociedad")).map((r) => r.Sociedad)),
    [opciones, mesFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro],
  );

  const gerenciasDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "gerencia")).map((r) => r.Gerencia)),
    [opciones, mesFiltro, sociedadFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro],
  );

  const subgerenciasDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "subgerencia")).map((r) => r.Subgerencia)),
    [opciones, mesFiltro, sociedadFiltro, gerenciaFiltro, unidadFiltro, cecoFiltro],
  );

  const unidadesDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "unidad")).map((r) => r.Unidad_Organizativa)),
    [opciones, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, cecoFiltro],
  );

  const cecosDisponibles = useMemo(
    () => uniqueSorted(opciones.filter((r) => coincideConFiltros(r, filtrosActivos, extraerValoresResumen, "ceco")).map((r) => r.Ceco)),
    [opciones, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro],
  );

  // Concepto solo existe en el detalle transaccional (no en "resumen"), asi
  // que se calcula aparte de filtrosActivos/coincideConFiltros — cascadea
  // igual contra los otros 6 filtros, pero no se autoexcluye porque no es
  // parte de ese set.
  const conceptosDisponibles = useMemo(
    () => uniqueSorted(detalleCompleto.filter((d) => coincideConFiltros(d, filtrosActivos, extraerValoresDetalle)).map((d) => d.Concepto)),
    [detalleCompleto, mesFiltro, sociedadFiltro, gerenciaFiltro, subgerenciaFiltro, unidadFiltro, cecoFiltro],
  );

  // Si al acotar un filtro la seleccion vigente de otro deja de tener sentido
  // (ej. eligo Sociedad y la Gerencia que tenia puesta no pertenece a esa
  // Sociedad), se limpia sola en vez de mandar al backend un cruce vacio.
  useEffect(() => {
    if (mesFiltro && !mesesDisponibles.includes(mesFiltro)) setMesFiltro("");
  }, [mesesDisponibles, mesFiltro]);
  useEffect(() => {
    const validos = sociedadFiltro.filter((v) => sociedadesDisponibles.includes(v));
    if (validos.length !== sociedadFiltro.length) setSociedadFiltro(validos);
  }, [sociedadesDisponibles, sociedadFiltro]);
  useEffect(() => {
    const validos = gerenciaFiltro.filter((v) => gerenciasDisponibles.includes(v));
    if (validos.length !== gerenciaFiltro.length) setGerenciaFiltro(validos);
  }, [gerenciasDisponibles, gerenciaFiltro]);
  useEffect(() => {
    const validos = subgerenciaFiltro.filter((v) => subgerenciasDisponibles.includes(v));
    if (validos.length !== subgerenciaFiltro.length) setSubgerenciaFiltro(validos);
  }, [subgerenciasDisponibles, subgerenciaFiltro]);
  useEffect(() => {
    const validos = unidadFiltro.filter((v) => unidadesDisponibles.includes(v));
    if (validos.length !== unidadFiltro.length) setUnidadFiltro(validos);
  }, [unidadesDisponibles, unidadFiltro]);
  useEffect(() => {
    const validos = cecoFiltro.filter((v) => cecosDisponibles.includes(v));
    if (validos.length !== cecoFiltro.length) setCecoFiltro(validos);
  }, [cecosDisponibles, cecoFiltro]);
  useEffect(() => {
    const validos = conceptoFiltro.filter((v) => conceptosDisponibles.includes(v));
    if (validos.length !== conceptoFiltro.length) setConceptoFiltro(validos);
  }, [conceptosDisponibles, conceptoFiltro]);

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

  const presupuestoAnualTotal = useMemo(
    () => sum(resumenAnualPresupuestado.map((r) => r.Presupuesto)),
    [resumenAnualPresupuestado],
  );

  // Real acumulado al ultimo mes cerrado, sumado sobre TODAS las cuentas que
  // entran en el alcance de los filtros generales activos (org: Sociedad/
  // Gerencia/Subgerencia/Unidad/Ceco — igual que el resto de "Saldo
  // disponible", no depende del filtro de Mes).
  const realAcumuladoTotal = useMemo(
    () =>
      sum(
        resumenAnualPresupuestado
          .filter((r) => r.Mes_Num === ultimoMesCerrado)
          .map((r) => r.Real_Acumulado),
      ),
    [resumenAnualPresupuestado, ultimoMesCerrado],
  );

  const saldoDisponibleTotal = presupuestoAnualTotal - realAcumuladoTotal;
  const pctGastado = presupuestoAnualTotal > 0 ? realAcumuladoTotal / presupuestoAnualTotal : 0;

  // Cuentas (Sociedad+Ceco+Cuenta+Gerencia+Subgerencia+Unidad) distintas en
  // el alcance de los filtros generales, y cuantas de esas NO tienen
  // presupuesto asignado — Con_Presupuesto_Asignado es el mismo para las 12
  // filas mensuales de una misma cuenta, alcanza con mirar la primera.
  const cuentasConSinPresupuesto = useMemo(() => {
    const combos = new Map<string, boolean>();
    for (const r of resumenAnual) {
      const key = `${r.Sociedad}|${r.Ceco}|${r.Cuenta_Contable}|${r.Gerencia}|${r.Subgerencia}|${r.Unidad_Organizativa}`;
      if (!combos.has(key)) combos.set(key, r.Con_Presupuesto_Asignado);
    }
    const total = combos.size;
    const sinPresupuesto = Array.from(combos.values()).filter((tiene) => !tiene).length;
    return { total, sinPresupuesto };
  }, [resumenAnual]);

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

  // Si hay un Mes filtrado, "resumen" ya viene acotado a ese unico mes (lo
  // haya cerrado o no) — usarlo tal cual. Sin filtro, se muestra por
  // defecto el ultimo mes CERRADO (el resumen trae los 12 meses del año,
  // incluyendo meses futuros sin cierre que no tiene sentido mostrar solos).
  const detalleMesActual = useMemo(() => {
    if (mesFiltro) return resumen;
    return resumen.filter((r) => r.Mes_Num === ultimoMesCerrado);
  }, [resumen, mesFiltro, ultimoMesCerrado]);

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

  const rankingImporte = useMemo(() => agregarPorPersona(detalle), [detalle]);

  const conceptosVisiblesRanking = useMemo(
    () => CONCEPTOS_RANKING.filter((c) => rankingImporte.some((p) => (p.PorConcepto[c] ?? 0) !== 0)),
    [rankingImporte],
  );
  const columnasRankingImporte = useMemo(
    () => construirColumnasRanking(conceptosVisiblesRanking),
    [conceptosVisiblesRanking],
  );

  const transaccionesOrdenadas = useMemo(
    () => ordenarFilas(rankingImporte, columnasRankingImporte, ordenColumnaTx, ordenAscTx),
    [rankingImporte, columnasRankingImporte, ordenColumnaTx, ordenAscTx],
  );

  function ordenarTransaccionesPor(id: string) {
    if (ordenColumnaTx === id) {
      setOrdenAscTx((prev) => !prev);
    } else {
      setOrdenColumnaTx(id);
      setOrdenAscTx(false);
    }
  }

  // Una fila por cuenta (Sociedad+Ceco+Cuenta+Gerencia+Subgerencia+Unidad),
  // quedandose con el mes mas reciente disponible segun los filtros activos
  // (si hay Mes filtrado, "resumen" ya trae un solo mes; si no, se usa el
  // ultimo con datos) — asi el % ejecutado acumulado refleja el estado
  // actual de cada cuenta y no se cuenta la misma cuenta varias veces.
  const cuentasActuales = useMemo(() => {
    const porCombo = new Map<string, Resumen>();
    for (const r of resumen) {
      if (!r.Con_Presupuesto_Asignado) continue;
      const key = `${r.Sociedad}|${r.Ceco}|${r.Cuenta_Contable}|${r.Gerencia}|${r.Subgerencia}|${r.Unidad_Organizativa}`;
      const actual = porCombo.get(key);
      if (!actual || r.Mes_Num > actual.Mes_Num) porCombo.set(key, r);
    }
    return Array.from(porCombo.values());
  }, [resumen]);

  const totalCuentas = cuentasActuales.length;

  // Presupuesto anual FIJO por cuenta (suma de las 12 filas mensuales de
  // Presupuesto, sin importar en que mes se cargo) — a diferencia de
  // Presupuesto_Acumulado (que ya viene en "resumen" pero es acumulado A LA
  // FECHA, la fuente de la distorsion que motiva el ritmo de ejecucion),
  // este numero es el mismo sin importar el mes que se este mirando.
  const presupuestoAnualPorCuenta = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of resumenAnualPresupuestado) {
      const key = `${r.Sociedad}|${r.Ceco}|${r.Cuenta_Contable}|${r.Gerencia}|${r.Subgerencia}|${r.Unidad_Organizativa}`;
      map.set(key, (map.get(key) ?? 0) + r.Presupuesto);
    }
    return map;
  }, [resumenAnualPresupuestado]);

  // Mes de referencia para "cuanto del año paso": si hay Mes filtrado, ese
  // mes; si no, el ultimo mes CERRADO real. OJO acá específicamente: NO se
  // puede usar r.Mes_Num de "cuentasActuales" cuando no hay filtro de mes,
  // porque "resumen" trae 12 filas por cuenta (universo completo del año,
  // con meses futuros en $0) y el dedup se queda con la de Mes_Num=12 aunque
  // el año real solo lleve, por ejemplo, 6 meses — usar esa fila haria creer
  // que ya paso todo el año, subestimando el ritmo real.
  const mesReferenciaRitmo = mesFiltro ? MESES_ORDEN.indexOf(mesFiltro) + 1 : ultimoMesCerrado;

  // Una cuenta entra en la tabla si CUALQUIERA de los dos indicadores la
  // marca (union, no interseccion) — asi se puede comparar cuenta por
  // cuenta cuando uno de los dos da alerta y el otro no.
  const cuentasEnAlerta = useMemo(() => {
    if (mesReferenciaRitmo <= 0) return [];
    const filas: CuentaConRitmo[] = [];
    for (const r of cuentasActuales) {
      const key = `${r.Sociedad}|${r.Ceco}|${r.Cuenta_Contable}|${r.Gerencia}|${r.Subgerencia}|${r.Unidad_Organizativa}`;
      const presupuestoAnual = presupuestoAnualPorCuenta.get(key) ?? 0;
      if (presupuestoAnual <= 0) continue;
      const pctTranscurrido = mesReferenciaRitmo / 12;
      const ritmo = r.Real_Acumulado / presupuestoAnual / pctTranscurrido;
      const proyeccionAnual = r.Real_Acumulado / pctTranscurrido;
      const pctGastado = r.Pct_Ejecucion_Acumulado ?? 0;
      if (pctGastado < UMBRAL_ADVERTENCIA && ritmo < RITMO_ADVERTENCIA) continue;
      filas.push({ ...r, presupuestoAnual, ritmo, proyeccionAnual, excedenteProyectado: proyeccionAnual - presupuestoAnual });
    }
    return filas;
  }, [cuentasActuales, presupuestoAnualPorCuenta, mesReferenciaRitmo]);

  const cantidadEnAlerta = cuentasEnAlerta.length;
  const pctEnAlerta = totalCuentas ? cantidadEnAlerta / totalCuentas : 0;

  const alertaOrdenada = useMemo(
    () => ordenarFilas(cuentasEnAlerta, COLUMNAS_ALERTA, ordenColumnaAlerta, ordenAscAlerta),
    [cuentasEnAlerta, ordenColumnaAlerta, ordenAscAlerta],
  );

  function ordenarAlertaPor(id: string) {
    if (ordenColumnaAlerta === id) {
      setOrdenAscAlerta((prev) => !prev);
    } else {
      setOrdenColumnaAlerta(id);
      setOrdenAscAlerta(false);
    }
  }

  const gastoPorConcepto = useMemo(() => {
    const map = groupSum(detalle, (d) => d.Concepto, (d) => d.Importe);
    return Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
  }, [detalle]);

  async function manejarExportar() {
    setExportando(true);
    setErrorExportar(null);
    try {
      await exportarDashboardHtml(opciones, userName);
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
        <div className="sobretiempo__export-banner">
          Reporte exportado el {datosExportados.generadoEl}
          {datosExportados.generadoPor && ` por ${datosExportados.generadoPor}`}.
        </div>
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
          <SearchableMultiSelect label="Sociedad" values={sociedadFiltro} options={sociedadesDisponibles} onChange={setSociedadFiltro} />
          <SearchableMultiSelect label="Gerencia" values={gerenciaFiltro} options={gerenciasDisponibles} onChange={setGerenciaFiltro} />
          <SearchableMultiSelect label="Subgerencia" values={subgerenciaFiltro} options={subgerenciasDisponibles} onChange={setSubgerenciaFiltro} />
          <SearchableMultiSelect label="Unidad" values={unidadFiltro} options={unidadesDisponibles} onChange={setUnidadFiltro} />
          <SearchableMultiSelect
            label="Centro Costo"
            values={cecoFiltro}
            options={cecosDisponibles}
            placeholder="Todos"
            onChange={setCecoFiltro}
            permitirSeleccionarTodo
          />
          <SearchableMultiSelect label="Concepto" values={conceptoFiltro} options={conceptosDisponibles} placeholder="Todos" onChange={setConceptoFiltro} />
          <SearchableSelect label="Mes" value={mesFiltro} options={mesesDisponibles} onChange={setMesFiltro} />
        </div>
      </div>

      <section>
        <h2>Resumen</h2>
        <div className="card">
          <h3>Saldo disponible</h3>
          <p className="sobretiempo__saldo-subtitulo">Según los filtros generales de arriba (Sociedad, Gerencia, Subgerencia, Unidad, Centro Costo).</p>
          <div className="sobretiempo__saldo-barra">
            <div
              className={`sobretiempo__saldo-barra-gastado${saldoDisponibleTotal < 0 ? " sobretiempo__saldo-barra-gastado--critico" : ""}`}
              style={{ width: `${Math.min(pctGastado, 1) * 100}%` }}
            >
              {pctGastado >= 0.08 && <span>Gastado</span>}
            </div>
            {saldoDisponibleTotal >= 0 && (
              <div className="sobretiempo__saldo-barra-disponible" style={{ width: `${(1 - pctGastado) * 100}%` }}>
                {1 - pctGastado >= 0.08 && <span>Disponible</span>}
              </div>
            )}
          </div>
          <div className="sobretiempo__saldo-datos">
            <div className="sobretiempo__saldo-dato">
              <span className="sobretiempo__saldo-dato-label">Gastado</span>
              <span className="sobretiempo__saldo-dato-valor">
                {formatCurrency(realAcumuladoTotal)} <span>({(pctGastado * 100).toFixed(1)}%)</span>
              </span>
            </div>
            <div className="sobretiempo__saldo-dato">
              <span className="sobretiempo__saldo-dato-label">Disponible</span>
              <span className={`sobretiempo__saldo-dato-valor ${saldoDisponibleTotal < 0 ? "negativo" : "positivo"}`}>
                {formatCurrency(saldoDisponibleTotal)}{" "}
                <span>({(100 - pctGastado * 100).toFixed(1)}%)</span>
              </span>
            </div>
            <div className="sobretiempo__saldo-dato">
              <span className="sobretiempo__saldo-dato-label">Presupuesto anual</span>
              <span className="sobretiempo__saldo-dato-valor">{formatCurrency(presupuestoAnualTotal)}</span>
            </div>
            <div className="sobretiempo__saldo-dato">
              <span className="sobretiempo__saldo-dato-label">Cuentas sin presupuesto</span>
              <span className="sobretiempo__saldo-dato-valor">
                {cuentasConSinPresupuesto.sinPresupuesto} de {cuentasConSinPresupuesto.total}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <h2>Control Mensual</h2>
        <div className="sobretiempo__panel-grid">
          <div className="card">
            <h3>Gasto real acumulado vs Presupuesto anual</h3>
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

        <div className="card sobretiempo__table-card">
          <h3>Ranking de Importe</h3>
          <p className="sobretiempo__alerta-subcifra sobretiempo__alerta-subcifra--intro">
            Una fila por persona, con el desglose por Concepto y el Total acumulado, dentro del
            alcance de los filtros actuales.
          </p>
          <div className="sobretiempo__table-wrap sobretiempo__table-wrap--scroll sobretiempo__table-wrap--rows10">
            <table>
              <thead>
                <tr>
                  {columnasRankingImporte.map((c) => (
                    <th key={c.id} title={c.titulo}>
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
                {transaccionesOrdenadas.map((d) => (
                  <tr key={d.Cod_SAP}>
                    {columnasRankingImporte.map((c) => (
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
        <h2>Alerta</h2>
        <div className="card sobretiempo__alerta-resumen-card">
          <h3>Cuentas en alerta</h3>
          <p className="sobretiempo__alerta-cifra">
            <strong>{cantidadEnAlerta}</strong>
            <span> de {totalCuentas}</span>
          </p>
          <p className="sobretiempo__alerta-subcifra">
            {(pctEnAlerta * 100).toFixed(1)}% de las cuentas con presupuesto asignado gastaron 50% o más de su
            presupuesto, o van a un ritmo que iguala o supera el presupuesto anual antes de fin de año.
          </p>
        </div>

        <div className="card sobretiempo__table-card">
          <h3>Ranking de cuentas % Gastado y Ritmo de gasto</h3>
          <p className="sobretiempo__alerta-subcifra sobretiempo__alerta-subcifra--intro">
            Se muestra cualquier cuenta marcada por alguno de los dos indicadores: % Gastado (sobre el presupuesto
            acumulado a la fecha) o Ritmo de gasto (proyectado a fin de año, no depende de en que mes estemos). Así
            se pueden comparar cuenta por cuenta.
          </p>
          {cuentasEnAlerta.length === 0 ? (
            <p className="sobretiempo__alerta-vacio">
              Ninguna cuenta está en alerta por % Gastado o Ritmo de gasto con los filtros actuales.
            </p>
          ) : (
            <div className="sobretiempo__table-wrap sobretiempo__table-wrap--scroll sobretiempo__table-wrap--rows10">
              <table className="sobretiempo__table--alerta">
                <thead>
                  <tr>
                    {COLUMNAS_ALERTA.map((c) => (
                      <th key={c.id}>
                        <button type="button" className="sobretiempo__th-sort" onClick={() => ordenarAlertaPor(c.id)}>
                          {c.label}
                          <span className="sobretiempo__sort-arrow">
                            {ordenColumnaAlerta === c.id ? (ordenAscAlerta ? "▲" : "▼") : ""}
                          </span>
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {alertaOrdenada.map((r, i) => (
                    <tr
                      key={i}
                      className={`sobretiempo__row--${nivelCombinado(r.Pct_Ejecucion_Acumulado ?? 0, r.ritmo)}`}
                    >
                      {COLUMNAS_ALERTA.map((c) => (
                        <td key={c.id}>{c.render(r)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <section>
        <h2>Detalle</h2>
        <div className="card">
          <div className="sobretiempo__table-wrap sobretiempo__table-wrap--scroll sobretiempo__table-wrap--rows20">
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
