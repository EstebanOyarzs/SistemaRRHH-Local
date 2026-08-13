import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import {
  actualizarDatos,
  descargarReporteExcel,
  getCambiosCargo,
  getCargosRevisar,
  getDotacion,
  getNuevosIngresos,
  getProcedimientos,
  guardarProcedimiento,
  type CambioCargo,
  type CargoRevisar,
  type Dotacion,
  type Procedimiento,
  type ResultadoActualizacion,
} from "../api/capacitacion";
import type { UserRole } from "../api/auth";
import { ApiError } from "../api/client";
import { ordenarFilas, type Columna } from "../utils/tablas";
import "./CapacitacionDashboardPage.css";

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

interface Orden {
  col: string;
  asc: boolean;
}

function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b, "es"));
}

function formatFecha(iso: string): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}-${m}-${y}`;
}

// Busca "Julio"/"julio" + un año de 4 digitos en el nombre del archivo, para
// prellenar el mes/año del reporte apenas se elige el archivo de dotacion
// actual — el admin lo puede corregir a mano si no matchea. Los nombres de
// mes en español no llevan tilde, asi que alcanza con comparar en minuscula.
function detectarMesAnio(filename: string): { mes: number; anio: number } | null {
  const normalizado = filename.toLowerCase();
  const mesIdx = MESES.findIndex((m) => normalizado.includes(m.toLowerCase()));
  const anioMatch = filename.match(/20\d{2}/);
  if (mesIdx === -1 || !anioMatch) return null;
  return { mes: mesIdx + 1, anio: Number(anioMatch[0]) };
}

async function cargarOVacio<T>(fn: () => Promise<T[]>): Promise<T[]> {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return [];
    throw err;
  }
}

const COLUMNAS_DOTACION: Columna<Dotacion>[] = [
  { id: "cod", label: "N° pers.", valor: (r) => r.Cod_Personal, render: (r) => r.Cod_Personal },
  { id: "nombre", label: "Nombre completo", valor: (r) => r.Nombre_Completo, render: (r) => r.Nombre_Completo },
  { id: "sociedad", label: "Sociedad", valor: (r) => r.Sociedad, render: (r) => r.Sociedad },
  { id: "unidad", label: "Unidad organizativa", valor: (r) => r.Unidad_Organizativa, render: (r) => r.Unidad_Organizativa },
  { id: "funcion", label: "Función", valor: (r) => r.Funcion, render: (r) => r.Funcion },
  { id: "gerencia", label: "Gerencia", valor: (r) => r.Gerencia, render: (r) => r.Gerencia },
  { id: "subgerencia", label: "Subgerencia", valor: (r) => r.Subgerencia, render: (r) => r.Subgerencia },
  { id: "ingreso", label: "Fecha Ingreso", valor: (r) => r.Fecha_Ingreso, render: (r) => formatFecha(r.Fecha_Ingreso) },
  { id: "clasificacion", label: "Clasificación", valor: (r) => r.Clasificacion, render: (r) => r.Clasificacion },
];

const COLUMNAS_CAMBIOS_CARGO: Columna<CambioCargo>[] = [
  { id: "cod", label: "N° pers.", valor: (r) => r.Cod_Personal, render: (r) => r.Cod_Personal },
  { id: "nombre", label: "Nombre completo", valor: (r) => r.Nombre_Completo, render: (r) => r.Nombre_Completo },
  { id: "sociedad", label: "Sociedad", valor: (r) => r.Sociedad, render: (r) => r.Sociedad },
  { id: "unidad", label: "Unidad organizativa", valor: (r) => r.Unidad_Organizativa, render: (r) => r.Unidad_Organizativa },
  { id: "cargo_anterior", label: "Cargo Anterior", valor: (r) => r.Cargo_Anterior, render: (r) => r.Cargo_Anterior },
  { id: "funcion", label: "Función", valor: (r) => r.Funcion, render: (r) => r.Funcion },
  { id: "gerencia", label: "Gerencia", valor: (r) => r.Gerencia, render: (r) => r.Gerencia },
  { id: "subgerencia", label: "Subgerencia", valor: (r) => r.Subgerencia, render: (r) => r.Subgerencia },
  { id: "clasificacion", label: "Clasificación", valor: (r) => r.Clasificacion, render: (r) => r.Clasificacion },
];

interface CapacitacionDashboardPageProps {
  userRole?: UserRole;
}

export function CapacitacionDashboardPage({ userRole }: CapacitacionDashboardPageProps = {}) {
  const [dotacion, setDotacion] = useState<Dotacion[]>([]);
  const [nuevosIngresos, setNuevosIngresos] = useState<Dotacion[]>([]);
  const [cambiosCargo, setCambiosCargo] = useState<CambioCargo[]>([]);
  const [cargosRevisar, setCargosRevisar] = useState<CargoRevisar[]>([]);
  const [procedimientos, setProcedimientos] = useState<Procedimiento[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const [ordenDotacion, setOrdenDotacion] = useState<Orden>({ col: "nombre", asc: true });
  const [ordenNuevos, setOrdenNuevos] = useState<Orden>({ col: "nombre", asc: true });
  const [ordenCambios, setOrdenCambios] = useState<Orden>({ col: "nombre", asc: true });

  const [busqueda, setBusqueda] = useState("");
  const [sociedadFiltro, setSociedadFiltro] = useState("");

  const [mostrarActualizar, setMostrarActualizar] = useState(false);
  const [archivoActual, setArchivoActual] = useState<File | null>(null);
  const [archivoAnterior, setArchivoAnterior] = useState<File | null>(null);
  const [mesReporte, setMesReporte] = useState(new Date().getMonth() + 1);
  const [anioReporte, setAnioReporte] = useState(new Date().getFullYear());
  const [actualizando, setActualizando] = useState(false);
  const [errorActualizar, setErrorActualizar] = useState<string | null>(null);
  const [resultadoActualizar, setResultadoActualizar] = useState<ResultadoActualizacion | null>(null);

  const [exportando, setExportando] = useState(false);
  const [errorExportar, setErrorExportar] = useState<string | null>(null);

  const [codigosCargoRevisar, setCodigosCargoRevisar] = useState<Record<string, string>>({});
  const [guardandoFuncion, setGuardandoFuncion] = useState<string | null>(null);
  const [errorMaestra, setErrorMaestra] = useState<string | null>(null);

  const [mostrarMaestra, setMostrarMaestra] = useState(false);
  const [busquedaMaestra, setBusquedaMaestra] = useState("");
  const [edicionesMaestra, setEdicionesMaestra] = useState<Record<string, string>>({});
  const [nuevaFuncion, setNuevaFuncion] = useState("");
  const [nuevoCodigo, setNuevoCodigo] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      cargarOVacio(getDotacion),
      cargarOVacio(getNuevosIngresos),
      cargarOVacio(getCambiosCargo),
      cargarOVacio(getCargosRevisar),
      getProcedimientos(),
    ])
      .then(([d, n, c, r, p]) => {
        if (cancelled) return;
        setDotacion(d);
        setNuevosIngresos(n);
        setCambiosCargo(c);
        setCargosRevisar(r);
        setProcedimientos(p);
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
  }, [refreshKey]);

  const sociedadesDisponibles = useMemo(() => uniqueSorted(dotacion.map((d) => d.Sociedad)), [dotacion]);

  const dotacionFiltrada = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return dotacion.filter((d) => {
      if (sociedadFiltro && d.Sociedad !== sociedadFiltro) return false;
      if (q && !`${d.Nombre_Completo} ${d.Funcion}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [dotacion, busqueda, sociedadFiltro]);

  const dotacionOrdenada = useMemo(
    () => ordenarFilas(dotacionFiltrada, COLUMNAS_DOTACION, ordenDotacion.col, ordenDotacion.asc),
    [dotacionFiltrada, ordenDotacion],
  );
  const nuevosOrdenados = useMemo(
    () => ordenarFilas(nuevosIngresos, COLUMNAS_DOTACION, ordenNuevos.col, ordenNuevos.asc),
    [nuevosIngresos, ordenNuevos],
  );
  const cambiosOrdenados = useMemo(
    () => ordenarFilas(cambiosCargo, COLUMNAS_CAMBIOS_CARGO, ordenCambios.col, ordenCambios.asc),
    [cambiosCargo, ordenCambios],
  );

  const procedimientosFiltrados = useMemo(() => {
    const q = busquedaMaestra.trim().toLowerCase();
    if (!q) return procedimientos;
    return procedimientos.filter((p) => p.Funcion.toLowerCase().includes(q));
  }, [procedimientos, busquedaMaestra]);

  function alternarOrden(actual: Orden, setActual: (v: Orden) => void, columnaId: string) {
    setActual(actual.col === columnaId ? { col: columnaId, asc: !actual.asc } : { col: columnaId, asc: true });
  }

  function manejarArchivoActual(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setArchivoActual(file);
    if (file) {
      const detectado = detectarMesAnio(file.name);
      if (detectado) {
        setMesReporte(detectado.mes);
        setAnioReporte(detectado.anio);
      }
    }
  }

  async function manejarProcesar() {
    if (!archivoActual || !archivoAnterior) {
      setErrorActualizar("Selecciona los 2 archivos de dotación (mes actual y mes anterior)");
      return;
    }
    setActualizando(true);
    setErrorActualizar(null);
    setResultadoActualizar(null);
    try {
      const resultado = await actualizarDatos(archivoActual, archivoAnterior, mesReporte, anioReporte);
      setResultadoActualizar(resultado);
      setArchivoActual(null);
      setArchivoAnterior(null);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setErrorActualizar(err instanceof ApiError ? err.message : "No se pudieron procesar los archivos");
    } finally {
      setActualizando(false);
    }
  }

  async function manejarExportar() {
    setExportando(true);
    setErrorExportar(null);
    try {
      await descargarReporteExcel();
    } catch (err) {
      setErrorExportar(err instanceof ApiError ? err.message : "No se pudo generar el reporte");
    } finally {
      setExportando(false);
    }
  }

  async function manejarGuardarCargoRevisar(funcion: string) {
    const codigos = (codigosCargoRevisar[funcion] ?? "").trim();
    if (!codigos) return;
    setGuardandoFuncion(funcion);
    setErrorMaestra(null);
    try {
      await guardarProcedimiento(funcion, codigos);
      setCargosRevisar((prev) => prev.filter((r) => r.Funcion !== funcion));
      setProcedimientos((prev) =>
        [...prev.filter((p) => p.Funcion !== funcion), { Funcion: funcion, Codigos: codigos }].sort((a, b) =>
          a.Funcion.localeCompare(b.Funcion, "es"),
        ),
      );
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setErrorMaestra(err instanceof ApiError ? err.message : "No se pudo guardar la clasificación");
    } finally {
      setGuardandoFuncion(null);
    }
  }

  async function manejarGuardarMaestra(funcion: string) {
    const codigos = (edicionesMaestra[funcion] ?? "").trim();
    if (!codigos) return;
    setGuardandoFuncion(funcion);
    setErrorMaestra(null);
    try {
      await guardarProcedimiento(funcion, codigos);
      setProcedimientos((prev) => prev.map((p) => (p.Funcion === funcion ? { ...p, Codigos: codigos } : p)));
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setErrorMaestra(err instanceof ApiError ? err.message : "No se pudo guardar la clasificación");
    } finally {
      setGuardandoFuncion(null);
    }
  }

  async function manejarAgregarMaestra() {
    const funcion = nuevaFuncion.trim();
    const codigos = nuevoCodigo.trim();
    if (!funcion || !codigos) return;
    setGuardandoFuncion(funcion);
    setErrorMaestra(null);
    try {
      await guardarProcedimiento(funcion, codigos);
      setProcedimientos((prev) =>
        [...prev.filter((p) => p.Funcion !== funcion), { Funcion: funcion, Codigos: codigos }].sort((a, b) =>
          a.Funcion.localeCompare(b.Funcion, "es"),
        ),
      );
      setNuevaFuncion("");
      setNuevoCodigo("");
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setErrorMaestra(err instanceof ApiError ? err.message : "No se pudo agregar la función");
    } finally {
      setGuardandoFuncion(null);
    }
  }

  if (loading) {
    return <p>Cargando...</p>;
  }

  if (error) {
    return <p className="capacitacion__error">{error}</p>;
  }

  return (
    <div className="capacitacion">
      <div className="capacitacion__header">
        <div>
          <h1>Capacitación</h1>
          <p className="capacitacion__subtitle">
            Nuevos ingresos, cambios de cargo y clasificación de procedimientos de capacitación por función.
          </p>
          <div className="capacitacion__export-action">
            <button type="button" className="btn" onClick={manejarExportar} disabled={exportando || dotacion.length === 0}>
              {exportando ? "Generando..." : "Descargar reporte (Excel)"}
            </button>
            {userRole === "administrador" && (
              <button
                type="button"
                className="btn capacitacion__btn-secundario"
                onClick={() => setMostrarActualizar((v) => !v)}
              >
                Actualizar datos
              </button>
            )}
            {errorExportar && <p className="capacitacion__error capacitacion__inline-error">{errorExportar}</p>}
          </div>

          {mostrarActualizar && (
            <div className="card capacitacion__panel-actualizar">
              <h3>Actualizar dotación</h3>
              <p className="capacitacion__subtitle">
                Sube la dotación del mes del reporte y la del mes anterior — el mes/año se detecta del nombre del
                archivo actual, pero se puede corregir antes de procesar.
              </p>
              <div className="capacitacion__form-grid">
                <label>
                  Dotación mes actual (ej. Julio)
                  <input type="file" accept=".xlsx" onChange={manejarArchivoActual} />
                </label>
                <label>
                  Dotación mes anterior (ej. Junio)
                  <input
                    type="file"
                    accept=".xlsx"
                    onChange={(e) => setArchivoAnterior(e.target.files?.[0] ?? null)}
                  />
                </label>
                <label>
                  Mes del reporte
                  <select value={mesReporte} onChange={(e) => setMesReporte(Number(e.target.value))}>
                    {MESES.map((m, i) => (
                      <option key={m} value={i + 1}>
                        {m}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Año
                  <input
                    type="number"
                    value={anioReporte}
                    onChange={(e) => setAnioReporte(Number(e.target.value))}
                  />
                </label>
              </div>
              <button type="button" className="btn" onClick={manejarProcesar} disabled={actualizando}>
                {actualizando ? "Procesando..." : "Procesar"}
              </button>
              {errorActualizar && <p className="capacitacion__error capacitacion__inline-error">{errorActualizar}</p>}
              {resultadoActualizar && (
                <p className="capacitacion__ok">
                  Dotación actualizada: {resultadoActualizar.dotacion.toLocaleString("es-CL")} personas,{" "}
                  {resultadoActualizar.nuevos_ingresos} nuevos ingresos, {resultadoActualizar.cambios_cargo} cambios
                  de cargo, {resultadoActualizar.cargos_revisar} cargos a revisar.
                  {resultadoActualizar.backup && " Se guardó un respaldo de la base anterior."}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {dotacion.length === 0 && (
        <p className="capacitacion__subtitle">
          Todavía no se cargó ninguna dotación.{" "}
          {userRole === "administrador"
            ? "Usa \"Actualizar datos\" para subir la primera."
            : "Pídele a un administrador que cargue la primera."}
        </p>
      )}

      <section>
        <h2>Nuevos ingresos</h2>
        <div className="card capacitacion__table-card">
          <div className="capacitacion__table-wrap">
            <table>
              <thead>
                <tr>
                  {COLUMNAS_DOTACION.map((c) => (
                    <th key={c.id}>
                      <button
                        type="button"
                        className="capacitacion__th-sort"
                        onClick={() => alternarOrden(ordenNuevos, setOrdenNuevos, c.id)}
                      >
                        {c.label}
                        <span className="capacitacion__sort-arrow">
                          {ordenNuevos.col === c.id ? (ordenNuevos.asc ? "▲" : "▼") : ""}
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {nuevosOrdenados.length === 0 ? (
                  <tr>
                    <td colSpan={COLUMNAS_DOTACION.length}>Sin nuevos ingresos este mes.</td>
                  </tr>
                ) : (
                  nuevosOrdenados.map((r) => (
                    <tr key={r.Cod_Personal}>
                      {COLUMNAS_DOTACION.map((c) => (
                        <td key={c.id}>{c.render(r)}</td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section>
        <h2>Cambios de cargo</h2>
        <div className="card capacitacion__table-card">
          <div className="capacitacion__table-wrap">
            <table>
              <thead>
                <tr>
                  {COLUMNAS_CAMBIOS_CARGO.map((c) => (
                    <th key={c.id}>
                      <button
                        type="button"
                        className="capacitacion__th-sort"
                        onClick={() => alternarOrden(ordenCambios, setOrdenCambios, c.id)}
                      >
                        {c.label}
                        <span className="capacitacion__sort-arrow">
                          {ordenCambios.col === c.id ? (ordenCambios.asc ? "▲" : "▼") : ""}
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cambiosOrdenados.length === 0 ? (
                  <tr>
                    <td colSpan={COLUMNAS_CAMBIOS_CARGO.length}>Sin cambios de cargo este mes.</td>
                  </tr>
                ) : (
                  cambiosOrdenados.map((r) => (
                    <tr key={r.Cod_Personal}>
                      {COLUMNAS_CAMBIOS_CARGO.map((c) => (
                        <td key={c.id}>{c.render(r)}</td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {cargosRevisar.length > 0 && (
        <section>
          <h2>Cargos a revisar ({cargosRevisar.length})</h2>
          <p className="capacitacion__subtitle">
            Funciones de la dotación actual que todavía no tienen códigos de procedimiento asignados.
          </p>
          <div className="card capacitacion__table-card">
            <div className="capacitacion__table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Función</th>
                    <th>Personas</th>
                    {userRole === "administrador" && <th>Código(s)</th>}
                  </tr>
                </thead>
                <tbody>
                  {cargosRevisar.map((r) => (
                    <tr key={r.Funcion}>
                      <td>{r.Funcion}</td>
                      <td>{r.Cantidad_Personas}</td>
                      {userRole === "administrador" && (
                        <td className="capacitacion__td-editable">
                          <input
                            type="text"
                            placeholder="ej. P-8211 / P-8212"
                            value={codigosCargoRevisar[r.Funcion] ?? ""}
                            onChange={(e) =>
                              setCodigosCargoRevisar((prev) => ({ ...prev, [r.Funcion]: e.target.value }))
                            }
                          />
                          <button
                            type="button"
                            className="btn capacitacion__btn-guardar"
                            disabled={guardandoFuncion === r.Funcion}
                            onClick={() => manejarGuardarCargoRevisar(r.Funcion)}
                          >
                            {guardandoFuncion === r.Funcion ? "..." : "Guardar"}
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {errorMaestra && <p className="capacitacion__error capacitacion__inline-error">{errorMaestra}</p>}
          </div>
        </section>
      )}

      <section>
        <h2>Dotación completa ({dotacionFiltrada.length})</h2>
        <div className="capacitacion__filters">
          <input
            type="text"
            placeholder="Buscar por nombre o función..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
          <select value={sociedadFiltro} onChange={(e) => setSociedadFiltro(e.target.value)}>
            <option value="">Todas las sociedades</option>
            {sociedadesDisponibles.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="card capacitacion__table-card">
          <div className="capacitacion__table-wrap capacitacion__table-wrap--scroll">
            <table>
              <thead>
                <tr>
                  {COLUMNAS_DOTACION.map((c) => (
                    <th key={c.id}>
                      <button
                        type="button"
                        className="capacitacion__th-sort"
                        onClick={() => alternarOrden(ordenDotacion, setOrdenDotacion, c.id)}
                      >
                        {c.label}
                        <span className="capacitacion__sort-arrow">
                          {ordenDotacion.col === c.id ? (ordenDotacion.asc ? "▲" : "▼") : ""}
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dotacionOrdenada.map((r) => (
                  <tr key={r.Cod_Personal}>
                    {COLUMNAS_DOTACION.map((c) => (
                      <td key={c.id}>{c.render(r)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section>
        <button type="button" className="capacitacion__toggle-seccion" onClick={() => setMostrarMaestra((v) => !v)}>
          {mostrarMaestra ? "▼" : "▶"} Tabla maestra de procedimientos ({procedimientos.length} funciones)
        </button>
        {mostrarMaestra && (
          <div className="card capacitacion__table-card">
            {userRole === "administrador" && (
              <div className="capacitacion__form-grid capacitacion__form-grid--agregar">
                <input
                  type="text"
                  placeholder="Función nueva"
                  value={nuevaFuncion}
                  onChange={(e) => setNuevaFuncion(e.target.value)}
                />
                <input
                  type="text"
                  placeholder="Código(s), ej. P-8211 / P-8212"
                  value={nuevoCodigo}
                  onChange={(e) => setNuevoCodigo(e.target.value)}
                />
                <button
                  type="button"
                  className="btn"
                  disabled={!nuevaFuncion.trim() || !nuevoCodigo.trim() || guardandoFuncion === nuevaFuncion.trim()}
                  onClick={manejarAgregarMaestra}
                >
                  Agregar
                </button>
              </div>
            )}
            <input
              type="text"
              className="capacitacion__buscador-maestra"
              placeholder="Buscar función..."
              value={busquedaMaestra}
              onChange={(e) => setBusquedaMaestra(e.target.value)}
            />
            <div className="capacitacion__table-wrap capacitacion__table-wrap--scroll">
              <table>
                <thead>
                  <tr>
                    <th>Función</th>
                    <th>Código(s)</th>
                  </tr>
                </thead>
                <tbody>
                  {procedimientosFiltrados.map((p) => (
                    <tr key={p.Funcion}>
                      <td>{p.Funcion}</td>
                      <td className="capacitacion__td-editable">
                        {userRole === "administrador" ? (
                          <>
                            <input
                              type="text"
                              value={edicionesMaestra[p.Funcion] ?? p.Codigos}
                              onChange={(e) =>
                                setEdicionesMaestra((prev) => ({ ...prev, [p.Funcion]: e.target.value }))
                              }
                            />
                            <button
                              type="button"
                              className="btn capacitacion__btn-guardar"
                              disabled={
                                guardandoFuncion === p.Funcion ||
                                (edicionesMaestra[p.Funcion] ?? p.Codigos) === p.Codigos
                              }
                              onClick={() => manejarGuardarMaestra(p.Funcion)}
                            >
                              {guardandoFuncion === p.Funcion ? "..." : "Guardar"}
                            </button>
                          </>
                        ) : (
                          p.Codigos
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
