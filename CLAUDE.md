# Sistema Web Local de Inteligencia Operacional

Sistema on-premise (notebook Windows) con dashboards, IA local, generación de informes y
automatización de Outlook. Corre en red local (LAN/VPN), sin publicar nada a Internet,
costo operativo $0, sin servicios de IA pagados.

Actuá como arquitecto de software senior y full-stack. Respetá las decisiones de
arquitectura de este archivo salvo limitación técnica real (como ya ocurrió con Entra ID,
ver "Desviaciones del diseño original").

## Desviaciones del diseño original

El diseño original preveía **Microsoft Entra ID + Microsoft Graph** para login y para
automatizar Outlook/OneDrive. El usuario **no tiene acceso a Azure AD administrador**
(ni siquiera para registrar una app básica), así que:

- **Autenticación**: reemplazada por login interno (usuario/clave en SQLite, JWT, bcrypt).
  Roles: `administrador`, `supervisor`, `usuario`, `consulta`. Ver `backend/auth/`.
- **Outlook**: en vez de Graph API, se automatiza el Outlook de escritorio instalado
  (Microsoft 365 Apps for Business ya está en esta máquina) vía **COM con `pywin32`**.
  Esto evita necesitar cualquier App Registration, porque Outlook desktop ya tiene sesión
  iniciada con autenticación moderna resuelta por el cliente. **Aún no implementado.**
- **OneDrive**: sin cambios respecto al diseño original — nunca se planeó usar Graph para
  esto, siempre fue leer la carpeta `onedrive_sync/` ya sincronizada localmente.

No reintroducir MSAL/Graph a menos que el usuario consiga acceso a Azure AD.

## Estado actual (ver tareas con TaskList para detalle fino)

Hecho:
- Estructura completa del proyecto, venv (Python 3.12), Node portable en PATH.
- Todas las dependencias backend instaladas (`backend/requirements.txt`), `pip check` limpio.
- FastAPI arranca (`backend/main.py`), config centralizada (`backend/config.py`, pydantic-settings).
- SQLite (`data/sistema.db`) + Alembic funcionando, migración inicial de `users` aplicada.
- **Módulo 1 (auth) completo y probado**: login, JWT, roles, endpoint protegido de creación
  de usuarios, script de bootstrap `backend/scripts/create_admin.py`.

- **Repo Git**: configurado y sincronizado. Remote `origin` en
  `https://github.com/EstebanOyarzs/SistemaRRHH-Local.git`, branch `master` al día.
- **Primer dashboard (Sobretiempo) — backend + frontend completos y probados**:
  ver "Patrón de dashboards" más abajo para el detalle de arquitectura backend,
  y "Frontend" para el detalle de la UI (React, ya inicializado).

- **Acceso multiusuario en LAN/VPN habilitado**: backend sirve tambien el build
  de produccion del frontend (mismo puerto), login con limite de 5 intentos.
  Ver seccion "Acceso en red (LAN/VPN)" mas abajo — incluye pasos manuales
  pendientes del lado del usuario (IP fija, firewall, nombre `pda`).

- **Segundo dashboard (Capacitación) — backend + frontend completos y probados**:
  ver "Dashboard de Capacitación" más abajo para el detalle completo (difiere
  del patrón de Sobretiempo en varios puntos: 2 archivos de dotación en vez
  de 1, y una tabla maestra editable con clasificación calculada en vivo).

- **Antivirus/EDR corporativo mata `venv\Scripts\python.exe` al escuchar red**
  (14-ago-2026): en esta notebook (Windows 11 Enterprise gestionada), el
  proceso de uvicorn se corta solo a los segundos/minutos de arrancar, sin
  traceback — pasa tanto en modo Producción (`0.0.0.0`) como Desarrollo
  (`127.0.0.1`), así que no es por estar expuesto en red. `node.exe` nunca
  se ve afectado. No se pudo confirmar 100% viendo el Historial de
  protección de Windows Security, pero el patrón (mata específicamente
  `python.exe` de un venv, nunca node) es consistente con un EDR que
  desconfía de intérpretes Python sin firmar. Mientras no se consiga una
  excepción de IT, el dashboard "se cae" impredeciblemente — la mitigación
  implementada es generar el reporte sin necesitar el servidor corriendo,
  ver "Reportes sin servidor" más abajo. `Iniciar.bat` (raíz del proyecto)
  tiene un menú Producción/Desarrollo con esperas y validaciones — sigue
  sufriendo el mismo problema del antivirus, no es un bug del script.

- **Dashboard de Sobretiempo — varias iteraciones de UX post-lanzamiento**
  (14-ago-2026, ver detalle completo en "Frontend" más abajo): filtros con
  selección múltiple (menos Mes), sección "Alerta" que combina dos
  indicadores (% Gastado y Ritmo de gasto, este último normalizado por
  tiempo transcurrido para no alertar más en diciembre que en enero),
  "Resumen" rediseñado como una sola barra de progreso, y "Concepto" ahora
  sale de la columna "Clasif Haber" del Excel (antes usaba el texto
  detallado "Texto expl.CC-nómina", que tenía ~20 variantes en vez de 5
  categorías limpias).

- **Tercer paso del pipeline de Sobretiempo: informes ejecutivos PDF por
  Gerencia** (17-ago-2026): ver "Reportes sin servidor" más abajo para el
  detalle completo — `Sobretiempo/generar_informes_gerencia.py`, un PDF por
  Gerencia con solo sus propios datos (KPIs, semáforo de Estado, evolución
  mensual, desglose por Subgerencia, gasto por Concepto y Ranking de
  Colaboradores), con iteraciones de UX post-lanzamiento el mismo día
  (celdas con salto de línea en vez de texto superpuesto, palabra de estado
  en vez de número/umbral para Ritmo de gasto, prefijo `(Alerta) ` en el
  nombre de archivo para las Gerencias sobre el ritmo esperado).

- **Bug de datos encontrado y corregido: `sobretiempo_resumen` sub-contaba
  el gasto real en cuentas con diferencias de mayúscula/minúscula entre
  hojas** (17-ago-2026, encontrado por el usuario comparando el dashboard
  HTML contra el informe PDF — Gerencia de Personas mostraba $3.600.948
  gastado en el HTML pero $9.930.397 en el PDF). Causa raíz: el criterio
  "con presupuesto asignado" está VALIDADO a nivel Ceco + Cuenta Contable
  (ver `enriquecer_detalle()` en `normalizar.py`, y ya lo usan correctamente
  `sobretiempo_detalle` y `sobretiempo_resumen_gerencia`), pero
  `construir_resumen()` (la función que arma `sobretiempo_resumen`, tabla
  que lee el panel "Resumen"/Alerta del dashboard Y el % Gastado del PDF)
  lo recalculaba por su cuenta agrupando por `KEY_ORG` completo (incluye
  Gerencia+Subgerencia+Unidad, no solo Ceco+Cuenta) — dos criterios
  distintos para el mismo campo. Cuando el mismo Ceco+Cuenta tiene
  presupuesto cargado bajo una Subgerencia ("Co Subgerencia de Personas")
  pero gasto real registrado bajo una variante con otra mayúscula ("CO
  Subgerencia de Personas", ~$6.3M en este caso), el criterio por
  `KEY_ORG` completo los trata como líneas distintas y el gasto de la
  variante sin match queda excluido del "% Gastado"/"Gastado" — sub-contando
  el dashboard HTML (el número correcto, validado, es el más alto: el que
  ya mostraba el PDF/`sobretiempo_resumen_gerencia`). Fix: `construir_resumen()`
  ahora calcula `Con_Presupuesto_Asignado` agrupando SOLO por
  Ceco+Cuenta_Contable, igual que `enriquecer_detalle()`. Se regeneraron
  `sobretiempo_resumen`/`sobretiempo_resumen_gerencia` directamente desde
  las tablas `sobretiempo_detalle`/`sobretiempo_presupuesto` ya cargadas
  (sin necesitar re-subir el Excel — `construir_resumen()` +
  `construir_resumen_gerencia()` corridos a mano sobre esas dos tablas,
  con `respaldar_db()` antes de sobrescribir). Verificado: ambas tablas
  ahora coinciden en $9.930.397 para Gerencia de Personas, y "% Gastado"
  del PDF pasó de 16.8% a 46.3% (ahora consistente con "% Ejecutado", que
  ya venía bien). **Esta discrepancia no era exclusiva de Sobretiempo de
  Personas** — cualquier Gerencia/Sociedad con una variante de mayúscula
  entre la hoja PPTO y la hoja DETALLE del Excel de origen puede tener el
  mismo problema; quedó corregido de raíz para toda carga futura, no solo
  para los datos ya cargados.

- **Tercer dashboard: Asistencia (GeoVictoria)** (18-ago-2026) — a diferencia
  de Sobretiempo/Capacitación, es un reporte HTML standalone sin backend/DB
  propia (decisión explícita del usuario). Ver sección "Dashboard de
  Asistencia (GeoVictoria)" más abajo para el detalle completo (gotchas de
  normalización del Excel de origen, alertas por persona con 3 niveles,
  identidad visual, filtros client-side en JS).

Pendiente (orden sugerido, ver spec original del usuario para el detalle de cada módulo):
1. Más planillas/dashboards siguiendo el mismo patrón que Sobretiempo/Capacitación
   (ver abajo), agregando su card en `frontend/src/pages/DashboardsHomePage.tsx`
   y su ruta/pagina.
2. Integración LM Studio (Qwen 2.5 3B) para consultas IA e informes. Se evaluó
   (13-ago-2026) un chat de consultas sobre la DB de Sobretiempo con
   function-calling + SQL libre de solo lectura como respaldo — no se llegó a
   implementar (el usuario canceló para priorizar el acceso en red), pero el
   diseño acordado queda como referencia si se retoma: preferir
   function-calling sobre los endpoints ya filtrados para preguntas de
   saldo/presupuesto (la lógica de negocio ya validada no se le puede confiar
   a un modelo de 3B), y dejar SQL libre (read-only, se le muestra la query
   al usuario) solo para preguntas descriptivas que los endpoints no cubren.
3. Automatización Outlook vía pywin32/COM (backend/email/).
4. Generación de reportes Excel/Word/PDF (backend/reports/).
5. Roles: por ahora solo se usa el rol `administrador` (decision del usuario,
   13-ago-2026). El sidebar/menu no tiene lógica condicional por rol todavía;
   cuando haya perfiles no-admin, hay que agregarla en `AppLayout.tsx`.

## Patrón de dashboards (establecido con Sobretiempo, replicar para los que sigan)

Cada dashboard es una planilla mensual que se normaliza y se carga a SQLite.
Para Sobretiempo (control de horas extra vs. presupuesto) quedó así:

- **Actualización mensual — dos formas, misma lógica** (definido con el
  usuario 13-ago-2026): la lógica de parsing/normalización (leer el Excel
  bruto "Control de Sobretiempo 2026.xlsx", hojas `DETALLE 2,0` y
  `PPTO 2026`, y armar las 4 tablas) vive en un solo lugar,
  `backend/dashboards/sobretiempo/normalizar.py` — nunca se duplica.
  1. **Botón "Actualizar datos (Excel)" en el dashboard** (solo visible para
     rol `administrador`): sube el Excel a `POST /dashboards/sobretiempo/actualizar`
     (multipart), el backend lo procesa y refresca el dashboard sin recargar
     la página. Es el flujo normal de uso.
  2. **`Sobretiempo/normalizar_sobretiempo.py`** (linea de comandos): wrapper
     delgado que llama a la misma funcion `procesar_archivo()` — uso de
     respaldo si no se tiene acceso a la pagina:
     `venv\Scripts\python.exe Sobretiempo\normalizar_sobretiempo.py "ruta\archivo.xlsx"`.

  Cada corrida (por cualquiera de las dos vías) REEMPLAZA por completo las 4
  tablas (el Excel de origen ya trae el acumulado del año, no hace falta
  mergear), pero **antes respalda la base anterior** en
  `Sobretiempo/data/backups/sobretiempo_<fecha>_<hora>.db` — si el archivo
  nuevo resulta tener un problema, se puede volver a copiar ese respaldo
  sobre `Sobretiempo/data/sobretiempo.db` mientras se soluciona (no hay botón
  de restaurar en la UI todavía, es copiar el archivo a mano). El Excel
  subido tambien queda archivado en `data/uploads/sobretiempo/` con
  timestamp, para trazabilidad de que archivo genero cada carga. Si el Excel
  tiene un formato inesperado (falta una hoja/columna), `procesar_archivo()`
  tira la excepcion ANTES de respaldar/reemplazar nada — la base vieja queda
  intacta y el usuario ve el error en el momento.
  `Sobretiempo/Archivos ejemplo/` tiene los insumos de referencia originales
  (Excel bruto, Excel normalizado viejo, HTML de ejemplo, script viejo que
  exportaba a Excel) — son solo referencia, no se tocan.
- **DB propia por dashboard**: cada dashboard tiene su propia SQLite
  (no comparte `data/sistema.db`, que es solo para `auth`). Vive físicamente
  dentro de la carpeta del dashboard (`Sobretiempo/data/sobretiempo.db`).
  Las tablas llevan el nombre del dashboard como prefijo
  (`sobretiempo_detalle`, `sobretiempo_presupuesto`, `sobretiempo_resumen`,
  `sobretiempo_resumen_gerencia`) — tablas siempre independientes entre
  dashboards, aunque puedan cruzarse en queries a futuro.
- **`backend/dashboards/sobretiempo/`**: acá vive el código que sí se integra
  al sistema central — `db.py` (engine SQLAlchemy apuntando al .db de arriba
  + constantes de nombre de tabla), `normalizar.py` (la logica de
  parsing/normalizacion, ver arriba — `respaldar_db()` + `procesar_archivo()`),
  `schemas.py` (Pydantic, un modelo por tabla con todas las columnas) y
  `router.py` (4 endpoints GET, uno por tabla, con filtros opcionales
  `anio`/`mes`/`sociedad`/`gerencia`/`subgerencia`/`unidad`/`ceco`/`cuenta`/
  `concepto` — todos menos `anio`/`mes` soportan selección múltiple (se
  mandan como parámetro repetido, `?sociedad=A&sociedad=B`), protegidos con
  `get_current_user` — cualquier rol autenticado puede leer; + `POST
  /actualizar`, protegido con `require_roles(ADMINISTRADOR)`, recibe el
  Excel subido). **Gotcha de FastAPI**: un campo `Optional[list[str]] =
  None` en un `@dataclass` usado con `Depends()` NO se llena solo desde
  query params repetidos — hace falta `Optional[list[str]] = Query(None)`
  explícito, si no siempre da `None` en silencio (sin error) aunque el
  campo `Optional[str] = None` normal sí funcione bien al lado. `Concepto`
  solo es válido para `sobretiempo_detalle` (no existe en las tablas
  pre-agregadas) — se ignora silenciosamente en las otras vía
  `TABLE_COLUMNS`, mismo mecanismo que ya usa `sobretiempo_resumen_gerencia`
  para ignorar filtros que no le aplican. Montado en `backend/main.py` bajo
  `/dashboards/sobretiempo/...`. Requiere `python-multipart` (ya en
  `requirements.txt`) para los uploads — si falta, FastAPI tira
  `RuntimeError` recien al registrar la ruta, no al arrancar.
- El HTML de ejemplo (`Sobretiempo_Dashboard.html`, Chart.js con los datos
  embebidos) mapea 1 a 1 con las 4 tablas: `resumenGerencia` → panel
  "Resumen Ejecutivo", `resumen` → paneles "Control Mensual" y "Detalle por
  Responsable", `detalle` → panel "¿En qué se gastó?". Sirve de referencia
  para qué campos va a necesitar el futuro frontend (el frontend real ya no
  usa `resumenGerencia`, ver "Frontend" más abajo).

## Reportes sin servidor (respaldo si el backend no se puede mantener arriba)

Por el problema del antivirus/EDR (ver "Estado actual"), cada dashboard
tiene un script de línea de comandos que genera el reporte final leyendo
la base SQLite y (para Sobretiempo) `frontend/dist` directo del disco —
**nunca abre un puerto de red**, así que no le pega el mismo problema.
Mismo patrón que `normalizar_*.py`: la lógica vive en
`backend/dashboards/<dashboard>/`, el script en la carpeta del dashboard es
un wrapper delgado.

- **Sobretiempo** (`Sobretiempo/generar_reporte_sobretiempo.py`): arma el
  MISMO HTML autocontenido que el botón "Descargar reporte (HTML)" del
  dashboard — lee los tags `<script>`/`<link>` de `frontend/dist/index.html`
  para ubicar el bundle JS/CSS del build, los embebe junto con
  `sobretiempo_resumen`/`sobretiempo_detalle` completas (`SELECT *`, sin
  filtrar) como `window.__PDA_EXPORT__`. La lógica vive en
  `backend/dashboards/sobretiempo/reporte_html.py`
  (`generar_reporte_html()`). Requiere `frontend/dist` ya compilado
  (`vite build`). Los booleanos de SQLite (0/1) se castean a `bool` de
  Python antes de convertir a JSON — si no, pandas los serializa como
  `0`/`1` en vez de `true`/`false`, y aunque el JS los trata igual por
  truthy/falsy, no coincidiría con lo que devuelve la API real. Guarda en
  `Sobretiempo/data/reportes/` (gitignored — el HTML lleva nombres/RUT
  reales de empleados). Nombre del archivo incluye el mes de LOS DATOS
  (ej. `Sobretiempo_Junio_2026_2026-08-17_132858.html`), no solo el
  timestamp de generación (17-ago-2026, a pedido del usuario) — el mes se
  calcula igual que en el PDF (`_ultimo_mes_anio()`, mismo criterio de
  "último mes cerrado" que usa `reporte_pdf.py`), porque el reporte se
  puede generar bastante después del cierre de los datos y el timestamp
  solo no dice a qué mes corresponde el contenido.
- **Capacitación** (`Capacitacion/generar_reporte_capacitacion.py`): arma
  el mismo Excel de 3 hojas que `GET /exportar-excel`. La lógica de armado
  del workbook (antes vivía duplicada dentro de `router.py`) se movió a
  `backend/dashboards/capacitacion/reporte_excel.py`
  (`generar_reporte_excel()`, `obtener_datos_reporte()`,
  `construir_workbook()`) — el endpoint HTTP y el script de consola llaman
  a las mismas funciones, nunca se duplica la lógica. Guarda en
  `Capacitacion/data/reportes/` (gitignored, mismo motivo).
- **Informes ejecutivos PDF de Sobretiempo, uno por Gerencia**
  (`Sobretiempo/generar_informes_gerencia.py`, 17-ago-2026): a diferencia
  del reporte HTML (que es el dashboard completo con todas las Gerencias),
  este genera un PDF liviano por Gerencia, con SOLO los datos de esa
  Gerencia — pensado para mandarle a cada gerente el estado de su propia
  área, sin que vea las demás. La lógica vive en
  `backend/dashboards/sobretiempo/reporte_pdf.py`
  (`generar_informes_gerencia()`), armado con `reportlab` (ya en
  `requirements.txt`, no depende de `frontend/dist` como el reporte HTML).
  Un PDF por cada Gerencia con al menos un mes cerrado en
  `sobretiempo_resumen_gerencia`. Estructura: KPIs (Presupuesto anual /
  Gasto acumulado / Saldo disponible / % Ejecutado), un semáforo de Estado,
  gráfico de evolución mensual (Real acumulado vs. línea de Presupuesto
  anual), desglose por Subgerencia (si tiene más de una), gasto por
  Concepto, y Ranking de Colaboradores (Top 10 por Importe acumulado en el
  año — agregado por persona, columnas Nombre/Cargo/Subgerencia/Importe/%,
  ver "Ranking de personas" abajo). Una página salvo Gerencias con muchas
  Subgerencias/personas, que pasan a 2 (probado con `gerencia_de_distribucion`,
  la más grande de las 19).
  - **Semáforo de Estado**: reusa la MISMA metodología y umbrales que la
    tabla "Alerta" del dashboard (ver "Frontend" más abajo) para el CALCULO
    interno — "% Gastado" = `Pct_Ejecucion_Acumulado` agregado desde
    `sobretiempo_resumen` (umbral 50%/70%) y "Ritmo de gasto" =
    `Real_Acumulado / Presupuesto_Total_Anual` normalizado por el mes
    transcurrido, agregado desde `sobretiempo_resumen_gerencia` (umbral
    1.0x/1.3x) — los dos numeros pueden diferir bastante entre sí (un caso
    real: 16.8% vs 46.3% en la misma Gerencia) porque miden cosas distintas,
    es esperado. **A diferencia del dashboard, el PDF NO muestra el numero
    ni el umbral del Ritmo** (a pedido del usuario, 17-ago-2026 — el numero
    es ruido para un gerente) — solo la palabra de estado resultante
    (`PROGRESO_LABEL` en `reporte_pdf.py`: "Progreso de gasto dentro de lo
    esperado" / "sobre lo esperado" / "excesivo a lo esperado"). "% Gastado"
    sí se sigue mostrando como número (no fue parte del pedido).
  - **Ranking de personas** (agregado 17-ago-2026 a pedido del usuario — a
    diferencia del resto del informe, este sí expone nombre y monto
    individual, es información sensible dentro de un documento ya
    confidencial/interno): Top 10 por Cod_SAP+Nombre, sumando Importe de
    TODO `sobretiempo_detalle` de la Gerencia en el año (no solo cuentas
    con presupuesto asignado, mismo criterio que "Gasto por Concepto").
  - **Prefijos en el nombre del archivo** para identificar casos especiales
    a simple vista en el explorador de Windows sin abrir cada PDF (el "("
    ordena alfabético antes que las letras, así quedan arriba de la lista):
    `(Alerta) Sobretiempo_...pdf` si el Ritmo de gasto agregado de la
    Gerencia es >= 1.0x (advertencia o crítico, mismo umbral que el
    semáforo; agregado 17-ago-2026), o `(Sin gasto) Sobretiempo_...pdf` si
    el Gasto acumulado de la Gerencia es exactamente $0 (agregado
    17-ago-2026, pedido a mitad de la sesión de la ronda de ajustes de UX
    de abajo). Son excluyentes entre sí (`Sin gasto` tiene prioridad, ya
    que si no hay gasto el Ritmo siempre da 0).
  - **Dos rondas de ajustes de UX/contenido** (17-ago-2026, mismo día del
    lanzamiento):
    - Ronda 1: título fusionado en una sola línea ("Informe de Sobretiempo
      {Gerencia}", ya no en un párrafo aparte); subtítulo cambiado de
      "Acumulado a {Mes} {Año}" a "Gasto a {Mes} {Año}"; el generador ya no
      usa `getpass.getuser()` (mostraba el usuario de Windows que corrió el
      script, ej. "eoyarzun") sino el texto fijo "Equipo de Compensaciones"
      (constante `GENERADO_POR` en `reporte_pdf.py`); el gráfico de
      Evolución mensual muestra el valor en pesos sobre cada punto de AMBAS
      líneas (Real acumulado y Presupuesto anual, vía
      `chart.lineLabelFormat`/`lineLabelNudge` de reportlab), y la leyenda
      del gráfico se armó con una muestra de línea real (`shapes.Line`) en
      vez de simular el trazo con caracteres de guion en el texto; pasada
      de ortografía en español latinoamericano (tildes: "atención",
      "crítico", "evolución", "ejecución", "año", "página", etc.) y
      eliminación de guiones largos (—) como puntuación en todo el texto
      visible del PDF, reemplazados por punto o coma según corresponda (el
      usuario fue explícito: "no dejes guiones, son . o ,").
    - Ronda 2: el nombre de la Gerencia en el título se probó en rojo
      (markup `<font color>` de `Paragraph`) y el usuario pidió volver
      atrás, mismo color navy que el resto del título; footer acortado de
      "Documento de uso interno. No distribuir fuera de la Gerencia." a
      "Documento de uso interno. No distribuir."; la frase explicativa del
      semáforo de Estado se acortó (era muy larga/poco clara) a "El Estado
      general combina dos indicadores: % Gastado (ejecución acumulada a la
      fecha) y Progreso de gasto (ritmo actual proyectado a fin de año).";
      más espaciado entre título/subtítulo/línea de "Generado el..." (venía
      muy apretado); se agregó una tabla "Mes / Gasto del mes / Gasto
      acumulado" debajo del gráfico de Evolución mensual porque el gráfico
      solo mostraba el acumulado, no el gasto puntual de cada mes
      (`_tabla_evolucion_mensual()`, usa el campo `Importe_Real_Mes` que ya
      traía `sobretiempo_resumen_gerencia` pero no se estaba usando); y se
      agregó el logo corporativo real (Chilquinta) en la cabecera —
      `assets/logo_chilquinta.jpg` (carpeta nueva en la raíz del proyecto,
      compartida entre dashboards, no es específica de Sobretiempo),
      insertado con `reportlab.platypus.Image`, tamaño calculado a partir
      de la proporción real del archivo vía `ImageReader.getSize()` en vez
      de hardcodear el aspect ratio (`_logo_flowable()` en
      `reporte_pdf.py`, devuelve `None` sin romper el informe si el
      archivo no está).
    - **Gotcha encontrado en esta ronda**: si el usuario tiene un PDF
      generado abierto en un visor (Edge, Acrobat, etc.) mientras se corre
      el generador de nuevo, Windows bloquea la escritura y
      `SimpleDocTemplate.build()` tira `PermissionError` — antes cortaba
      toda la corrida (ninguna Gerencia después de la bloqueada se
      generaba). Ahora `generar_informes_gerencia()` atrapa ese error por
      Gerencia, imprime un aviso, y sigue con las demás.
    - Ronda 3: el logo pasó a ir ARRIBA del título (apilado, tipo membrete),
      no al costado en una tabla de 2 columnas como había quedado en la
      Ronda 2 (`_logo_flowable()` ahora es un flowable más en el `story`,
      antes del bloque de título, sin `Table` envolvente); se sacó la
      columna "Trab. HE" (Trabajadores con Horas Extra) de la tabla
      Desglose por Subgerencia, a pedido del usuario; el título "Ranking de
      Colaboradores (Top 10 por Importe)" se acortó a solo "Ranking de
      Colaboradores" (el Top 10 se mantiene en la lógica, solo se sacó del
      texto visible); en el gráfico de Evolución mensual, la línea de
      Presupuesto anual (que repetía el mismo monto en los 12 puntos) dejó
      de mostrar un valor por punto — ahora el monto se muestra UNA sola
      vez, centrado arriba del gráfico ("Presupuesto anual: $XXX.XM"), la
      línea Real acumulado sigue con su valor en cada punto; se agregó una
      barra de progreso horizontal roja (Gastado) + verde (Disponible)
      debajo de los KPIs (`_barra_progreso()`), calcada del panel "Resumen"
      del dashboard HTML, y una línea divisoria roja debajo de cada título
      de sección (helper `seccion()` local a `_construir_pdf`, usa
      `HRFlowable`) para acercar el look del PDF al de las tarjetas del
      dashboard, a pedido del usuario ("evalua una mejora visual, que sea
      simil al diseño del informe general html").
    - **Gotcha de reportlab encontrado en la Ronda 3**: `chart.lineLabelArray`
      (para poner un texto de label distinto por punto, incluido `None`
      para no dibujar nada en un punto puntual) NO se usa a menos que
      `chart.lineLabelFormat` sea el string literal `"values"` — con
      `lineLabelFormat=None` (el default) no se dibuja NINGÚN label sin
      importar lo que tenga `lineLabelArray`, aunque no tira ningún error
      (se ve como que el atributo simplemente no hizo nada). Confirmado
      leyendo el código fuente de `HorizontalLineChart._innerDrawLabel` en
      la librería.
    - Ronda 4: se sacó por completo la barra de progreso Gastado/Disponible
      agregada en la Ronda 3 (`_barra_progreso()` eliminada del código, no
      solo del `story` — el usuario no la quiso en el PDF, a diferencia del
      dashboard HTML donde sí queda); "Ranking de Colaboradores" pasó a
      "Ranking de Colaboradores con mayores gastos"; título/subtítulo/línea
      de "Generado el..." pasaron a centrados (`alignment=TA_CENTER` en los
      3 `ParagraphStyle`) y el logo también se centró horizontalmente
      (`logo.hAlign = "CENTER"`), para que el título quede alineado con el
      logo arriba (ambos centrados en el ancho de la página, ya no
      alineados a la izquierda).
    - Ronda 5: cada sección (título + línea divisoria + contenido: tabla,
      gráfico, nota) se envuelve en `reportlab.platypus.KeepTogether` — si
      no entra completa en lo que queda de la página actual, reportlab la
      pasa entera a la página siguiente en vez de cortarla a mitad de tabla
      o gráfico, a pedido del usuario. Probado con la Gerencia más grande
      (Distribución, 4 Subgerencias + 4 Conceptos + Ranking de 10): la
      página 1 corta limpio después de "Evolución mensual" y la página 2
      arranca con "Desglose por Subgerencia" completo. Ojo: `KeepTogether`
      solo garantiza "empezar en página nueva si no entra en la actual" —
      si una sección fuera más alta que una página entera igual se
      partiría (no ocurre hoy con los datos reales, pero es la limitación
      de la técnica, no da una garantía absoluta).
    - Ronda 6 (cambio de alcance, no solo UX): el informe distingue
      **Opex vs. Capex por Centro de Costo** — un Ceco es Opex si termina
      en "10099", Capex si no (incluye "SIN CECO (Cargo a Proyecto)"),
      criterio dado por el usuario. **TODO el informe queda acotado a
      Opex** (KPIs, Estado, Evolución mensual, Subgerencias, Concepto,
      Ranking principal) — Capex solo aparece al final, como sección
      complementaria "Ranking Capex" (mismo Top 10 por Importe, pero
      calculado solo sobre Ceco Capex, con nota aclaratoria de que es
      información complementaria). Esto obligó a cambiar la FUENTE de
      datos de KPIs/Estado/Subgerencias/Evolución: pasaron de
      `sobretiempo_resumen_gerencia` (agregada a nivel Gerencia+
      Subgerencia+Mes, SIN columna Ceco — no se puede partir Opex/Capex) a
      `sobretiempo_resumen` (nivel Ceco+Cuenta+Mes, sí tiene Ceco),
      replicando en pandas la misma agregación por Subgerencia que antes
      hacía `construir_resumen_gerencia()` en `normalizar.py` (ver
      `_datos_gerencia()` en `reporte_pdf.py`). El campo "Trabajadores con
      HE" se eliminó del todo en este cambio (ya no se mostraba en ningún
      lado desde la Ronda 3, y `sobretiempo_resumen` no tiene esa columna
      para recalcularlo). Validación cruzada interesante: en la práctica,
      Capex resultó ser casi 1:1 con el cargo "Projects" y Opex con
      "Payroll" en los datos reales — refuerza que el criterio del sufijo
      del Ceco es correcto.
    - **Gotcha de pandas encontrado en la Ronda 6**: filtrar un DataFrame
      de 0 filas con una máscara booleana (ej. `df[serie_booleana]`) hace
      que pandas descarte TODAS las columnas si tanto el DataFrame como la
      máscara están vacíos — el resultado queda con 0 filas Y 0 columnas,
      aunque el DataFrame original sí tenía sus columnas. Rompía con
      `KeyError: 'Importe'` para Gerencias sin ningún registro en
      `sobretiempo_detalle` (ej. "Gerencia de Adquisiciones"). Fix: si
      `det.empty`, saltear el filtrado Opex/Capex y usar el mismo
      DataFrame vacío (con columnas) para ambos — da lo mismo Opex que
      Capex cuando no hay ninguna fila.
    - Ronda 7 (17-ago-2026): "Ranking de Colaboradores con mayores gastos"
      y "Ranking Capex" pasaron al MISMO diseño pivoteado que el "Ranking
      de Importe" del dashboard HTML (ver más abajo, "Frontend") — una
      fila por persona con una columna de Importe por Concepto (Hora
      Extra, Turnos, Citación, etc.) + columna Total, en vez de una sola
      columna "Importe" (que ya sumaba todo por persona, pero sin abrir el
      detalle por concepto). `_ranking_por_concepto()` reemplaza a la
      función `_ranking()` anterior — agrupa por Cod_SAP+Nombre+Concepto,
      pivotea Concepto a columnas, calcula Total por separado (sumando
      TODO el Importe de la persona, no solo `CONCEPTOS_RANKING` conocidos,
      por si aparece una categoría nueva no listada) y se queda con el Top
      10 por Total. `_tabla_ranking()` oculta las columnas de Concepto en
      $0 para TODAS las personas mostradas (igual criterio que el
      dashboard) — por eso "Ranking de Colaboradores" y "Ranking Capex" de
      un mismo informe pueden mostrar distintas columnas de Concepto entre
      sí (ej. Capex nunca tuvo "Rot Horas Extra/Turnos" en los datos
      reales de Distribución, esa columna no aparece ahí pero sí en el
      ranking Opex). `CONCEPTOS_RANKING`/`LABEL_CONCEPTO_CORTO` quedaron
      duplicados en Python (`reporte_pdf.py`) y TypeScript
      (`SobretiempoDashboardPage.tsx`) — son proyectos separados sin canal
      de constantes compartidas, hay que actualizar los dos si la lista de
      Concepto cambia. Se sacaron las columnas Cargo/Subgerencia/% del
      ranking del PDF (no entraban junto con las columnas de Concepto en
      el ancho de página) — si hace falta ese detalle, está en la tabla
      "Desglose por Subgerencia" de más arriba en el mismo informe.
    - Ronda 8 (17-ago-2026): se agregó columna **"Horas"** (Cantidad_Horas
      total, no desglosada por Concepto) tanto al "Ranking de Importe" del
      HTML como a "Ranking de Colaboradores"/"Ranking Capex" del PDF — el
      usuario pidió poder ver el total de horas extra de cada trabajador,
      no solo el monto. En el HTML, `PersonaImporte.Horas` se acumula en
      `agregarPorPersona()` igual que `Total`, columna nueva entre
      Gerencia y el desglose por Concepto. En el PDF,
      `_ranking_por_concepto()` agrega `Horas` vía `.agg(Total=...,
      Horas=("Cantidad_Horas", "sum"))`, columna nueva entre Nombre y el
      desglose por Concepto (hubo que sumar `Cantidad_Horas` al `SELECT`
      de `sobretiempo_detalle` en `_datos_gerencia()`, antes no se traía).
  - **Celdas de tabla envueltas en `Paragraph`, nunca strings planos**
    (gotcha encontrado 17-ago-2026): un string plano dentro de una celda de
    `Table` de reportlab NO hace salto de línea — si el texto no entra en
    el ancho de columna, se sale de la celda y se dibuja encima de la
    columna de al lado (texto superpuesto/ilegible). Pasaba con nombres de
    Subgerencia largos ("Subgerencia de Mantenimiento de Distribución") y
    con la línea larga del semáforo de Estado. Fix: helper `_celda()` en
    `reporte_pdf.py` envuelve todo texto de celda en un `Paragraph` (con
    `xml.sax.saxutils.escape()` porque `Paragraph` interpreta un subset de
    HTML), que sí hace salto de línea dentro del ancho de columna. Aplica a
    cualquier tabla nueva de este informe o de futuros reportes PDF.
  - Guarda en `Sobretiempo/data/reportes/gerencias/` (gitignored, mismo
    motivo que los otros reportes — nombres/montos reales por persona y
    área). Probado 17-ago-2026 contra la base real (19 Gerencias).
- Los comandos completos (con rutas absolutas, listos para copiar) están en
  `Sobretiempo/Ejecutar.txt` y `Capacitacion/Ejecutar.txt`.

## Dashboard de Capacitación

Segundo dashboard (14-ago-2026). Cruza la Dotación de Chilquinta y Filiales
contra una tabla maestra Función→Códigos de procedimiento de capacitación,
para saber a quién capacitar cada mes. Difiere del patrón de Sobretiempo en
varios puntos — documentados acá porque no son obvios releyendo el código:

- **Insumo mensual = 2 archivos, no 1**: la dotación del mes del reporte
  ("actual") y la del mes anterior — necesarios para detectar cambios de
  cargo por comparación. **Se suben ambos a mano** desde el botón
  "Actualizar datos" del dashboard (2 `<input type="file">` + selector de
  Mes/Año del reporte, prellenado parseando el nombre del archivo "actual"
  — los nombres de mes en español no llevan tilde así que alcanza un
  `.toLowerCase().includes()`, sin normalizar Unicode). El sistema **no lee
  `Dotacion/` automáticamente**, aunque esa carpeta exista sincronizada
  localmente — decisión explícita del usuario, no una limitación técnica.
- **Columnas del Excel de dotación seleccionadas por POSICIÓN, no por
  nombre**: la hoja "Detalle..." cambia de nombre mes a mes ("Detalle
  Activos", "Detalle activos", "Detalle Chilquintas y Filiales") y sus
  encabezados se leen con acentos corruptos según la codificación de
  consola de Windows. Se verificó a mano que las 12 columnas necesarias
  están en la MISMA posición (0,1,5,6,10,11,12,13,14,32,33,34) en los 5
  archivos de 2026 disponibles a la fecha — `backend/dashboards/capacitacion/normalizar.py`
  (`COL_POSICIONES`) depende de que esto se mantenga; si Talento Humano
  cambia el formato del Excel de dotación (agrega/quita una columna antes
  de la posición 34), hay que volver a mapear las posiciones.
- **Tabla maestra Función→Código editable en el sistema**
  (`capacitacion_procedimientos`, `Funcion` como PRIMARY KEY): se siembra
  UNA SOLA VEZ, al arrancar el backend, leyendo la hoja "Procedimientos" del
  Excel de referencia más completo (`Capacitacion/Archivos Ejemplo/Reporte
  para capacitaciones - Mayo 2026.xlsx`, 572 funciones únicas — ese archivo
  no se vuelve a tocar ni se referencia en ningún otro lado). De ahí en más
  se edita a mano desde la UI (`PUT /dashboards/capacitacion/procedimientos`,
  solo admin) — ya sea clasificando un "cargo a revisar" en el momento, o
  editando/agregando una fila directamente en la sección colapsable "Tabla
  maestra de procedimientos".
- **La Clasificación de Procedimientos y los "cargos a revisar" se calculan
  EN VIVO, nunca se guardan como snapshot**: `capacitacion_dotacion`,
  `capacitacion_nuevos_ingresos` y `capacitacion_cambios_cargo` guardan la
  dotación cruda (sin columna de clasificación); cada lectura
  (`GET /dotacion`, `/nuevos-ingresos`, `/cambios-cargo`, `/exportar-excel`)
  hace `LEFT JOIN` contra `capacitacion_procedimientos` al vuelo
  (`_query_con_clasificacion` en `router.py`), y "cargos a revisar" es un
  `LEFT JOIN ... WHERE p.Funcion IS NULL` (`_cargos_revisar_en_vivo`). Esto
  fue un cambio de diseño respecto al primer intento (que guardaba la
  clasificación calculada al momento de subir el Excel): con snapshot, un
  admin clasificando un cargo nuevo no se veía reflejado en ningún lado
  (ni en la Dotación completa ni en el Excel exportado) hasta la
  **próxima carga mensual** — con cálculo en vivo, se refleja al instante
  en todas las vistas apenas se guarda, sin tener que volver a subir nada.
- **Criterios exactos** (verificados a mano contra
  `Dotacion/2026/*.xlsx` y `Capacitacion/Archivos Ejemplo/*.xlsx`):
  "Nuevos ingresos" = personas de la dotación actual cuya `Fecha_Ingreso`
  cae en el Mes/Año del reporte (el que se eligió en el selector, no el mes
  calendario actual). "Cambios de cargo" = personas presentes en ambas
  dotaciones (mismo `Cod_Personal`) cuya `Funcion` difiere entre el mes
  anterior y el actual — `Cargo_Anterior` es la función del mes anterior.
  "Cargos a revisar" = funciones de la dotación actual que no existen en la
  tabla maestra (a diferencia de una función que SÍ está en la tabla maestra
  pero con el valor placeholder "Revisar si aplican procedimientos" — eso
  es un cargo ya catalogado como sin-código-todavía, no aparece en esta
  lista, es un estado normal que puede persistir).
- **Excel exportado (`GET /exportar-excel`) generado 100% server-side con
  openpyxl** (a diferencia del export HTML de Sobretiempo, que reusa el
  bundle JS de la app en vivo) — arma un `.xlsx` real con las mismas 3 hojas
  que `Capacitacion/Archivos Ejemplo/*.xlsx` (`Resumen` con las tablas de
  Nuevos ingresos + Cambios de cargo apiladas, `Dotación CHTA`,
  `Procedimientos`), devuelto como `StreamingResponse`. Nombre de archivo
  `Reporte para capacitaciones - {Mes} {Año}.xlsx`, usando el
  `Mes_Reporte`/`Anio_Reporte` guardados en `capacitacion_dotacion` (los
  únicos 2 campos "no crudos" que sí persiste esa tabla).
- **DB propia** `Capacitacion/data/capacitacion.db`, con
  `Capacitacion/data/backups/` (respaldo antes de cada `/actualizar`,
  igual que Sobretiempo) y `data/uploads/capacitacion/` (archiva ambos
  Excel subidos, con timestamp).
- `backend/dashboards/capacitacion/`: `db.py` (engine + nombres de tabla +
  `CREATE TABLE IF NOT EXISTS` de la tabla maestra al importar), `normalizar.py`
  (parsing + `sembrar_procedimientos_si_vacia()` + `procesar_archivos()`),
  `reporte_excel.py` (armado del workbook de 3 hojas, compartido entre
  `GET /exportar-excel` y el script de consola, ver "Reportes sin
  servidor"), `schemas.py`, `router.py`. Montado en `backend/main.py` bajo
  `/dashboards/capacitacion/...`; `sembrar_procedimientos_si_vacia()` se
  llama una vez ahí mismo, después de montar el router.
- **`Capacitacion/normalizar_capacitacion.py`** (línea de comandos, 14-ago-2026):
  wrapper delgado sobre `procesar_archivos()`, mismo rol que
  `Sobretiempo/normalizar_sobretiempo.py` — uso:
  `venv\Scripts\python.exe Capacitacion\normalizar_capacitacion.py "actual.xlsx" "anterior.xlsx" <mes> <anio>`.
- Frontend: `frontend/src/pages/CapacitacionDashboardPage.tsx` +
  `frontend/src/api/capacitacion.ts`. El helper genérico de tablas
  ordenables (`Columna<T>`, `ordenarFilas`) se movió a
  `frontend/src/utils/tablas.ts` (antes vivía duplicado dentro de
  `SobretiempoDashboardPage.tsx`) para que ambos dashboards lo compartan.

## Dashboard de Asistencia (GeoVictoria) — reporte standalone, sin backend

Tercer dashboard (18-ago-2026), pero con una decisión de arquitectura distinta
a Sobretiempo/Capacitación: **NO sigue el "Patrón de dashboards"** (sin SQLite
propia, sin router en `backend/`, sin página en `frontend/`) — es un único
script Python que genera un HTML autocontenido, decisión explícita del
usuario al elegir entre las dos opciones planteadas ("reporte HTML rápido" vs.
"módulo completo integrado al sistema"). Si en el futuro se quiere el patrón
completo (carga mensual vía botón, multiusuario en red, DB propia), hay que
construirlo desde cero — este script no se pensó como base para eso.

- **Qué es**: reporte de asistencia (control de ingreso/salida) a partir del
  Excel "Gestión de Asistencia" que exporta el sistema GeoVictoria (transaccional,
  una fila por persona+día). `Geovictoria/generar_reporte_asistencia.py`:
  `venv\Scripts\python.exe Geovictoria\generar_reporte_asistencia.py "ruta\archivo.xlsx"`
  (sin argumento, usa el Excel de ejemplo en `Geovictoria\Archivos ejemplo\`).
  Guarda en `Geovictoria/data/reportes/` (gitignored, mismo motivo que
  Sobretiempo/Capacitación — nombres/RUT reales). `Geovictoria/Archivos
  ejemplo/*.xlsx` también gitignored.
- **Toda la agregación vive en JavaScript, no en Python** (a diferencia de
  Sobretiempo/Capacitación): `construir_datos_reporte()` en Python solo arma
  `fecha_corte` + el detalle fila-por-fila (persona+día, con nombres de campo
  cortos: `id/n/g/f/d/p/fcp/me/ms/am/lj/ht`) + listas de opciones para los
  filtros. El HTML embebido recalcula KPIs/gráficos/tablas en el navegador
  cada vez que cambia un filtro (`recalcular()` en `APP_JS`, dentro del mismo
  archivo `.py`) — mismo patrón visual/UX que los filtros en cascada de
  Sobretiempo, pero reimplementado en JS vanilla porque este reporte no reusa
  ningún bundle de React (es 100% standalone). Si se cambia una regla de
  negocio (ej. un umbral de alerta), hay que tocarla en el JS, Python ya no
  tiene esa lógica.
- **Filtros**: Unidad (= columna `Grupo` del Excel, renombrada en la UI),
  Nombre y Apellido, Mes, Día — los primeros dos multi-selección con
  buscador (componente `crearMultiSelect` en el JS embebido), Mes/Día también
  multi-selección pero sin cascada entre sí (a diferencia de Sobretiempo, acá
  las opciones de cada filtro son fijas, no se recalculan según los demás
  filtros activos). Barra de filtros con `position: sticky; top: 0`.
- **Gotchas de los datos de GeoVictoria, encontrados normalizando el Excel real**:
  - **Un "Permiso" puede ser un beneficio permanente** (ej. "Amamantamiento")
    que GeoVictoria marca en TODOS los días del mes de la persona, no solo el
    día que realmente faltó — la persona igual marca entrada y trabaja normal
    (con derecho a llegar más tarde). Por eso "falta explicada por permiso"
    (`Falta_Con_Permiso`) exige ADEMÁS que no haya marcaje ese día puntual; si
    hay Entrada marcada, cuenta como día asistido sin importar qué Permiso
    tenga activo. Sin este chequeo, el % de Asistencia daba 0% para gente que
    en realidad asistía todos los días.
  - **"Atraso" ya viene en 0 desde GeoVictoria cuando hay justificación
    escrita** (columna "Justificado" con texto tipo "trafico en ruta", "cita
    medica") — comprobado contra el Excel real: NINGUNA fila con
    justificación tiene `Atraso > 0`, aunque la hora de entrada sea
    objetivamente posterior al inicio de turno. O sea, los atrasos que se
    cuentan YA excluyen por diseño del propio Excel las llegadas tarde
    perdonadas — no hace falta (ni se puede) filtrar "atrasos justificados"
    aparte. La justificación se guarda solo como métrica informativa aparte
    ("Llegadas justificadas").
  - **No se rastrea colación**: el Excel trae dos pares Entró/Salió (uno para
    colación, otro para el día completo) pero a pedido del usuario el reporte
    no distingue entre ellos — "marcó salida" = tiene CUALQUIERA de las dos
    salidas marcadas. Sin este criterio, ~2000 filas por mes salían como
    "sin marcaje de salida" solo porque la persona no marca colación por
    separado (usa un solo Entró/Salió para todo el día), un falso positivo
    enorme.
  - **"Marcaje incompleto"** (entró pero nunca marcó ninguna salida) excluye
    el día de corte (hoy/último día con datos) — si no, todo el que llegó hoy
    y aún no se fue aparece como "incompleto" aunque su jornada siga en curso
    al momento de generar el reporte.
  - **Valores de "Permiso" compuestos y sucios**: ej. `"Vacaciones;
    Vacaciones"` (mismo permiso repetido con `;`) — `_normalizar_permiso()`
    en `cargar_datos()` dedupea antes de agregar, si no el donut de "Uso de
    permisos por tipo" contaba "Vacaciones" y esa variante como categorías
    separadas.
- **Alertas de asistencia**: tabla por persona con 3 niveles (Crítico /
  Advertencia / **Leve**), combinando atrasos no justificados + ausencias
  injustificadas + días sin marcaje de salida — "el peor de los tres
  indicadores" gana. El nivel **Leve** (18-ago-2026, agregado a pedido del
  usuario) es clave: sin él, alguien con 1-3 incidencias por debajo del
  umbral de Advertencia no aparecía en la tabla aunque el KPI de arriba
  mostrara `> 0` — confundía, sobre todo filtrando por un solo Día (donde los
  umbrales absolutos casi nunca se alcanzan). Columna "Motivo" arma el texto
  explicando cuál(es) indicador(es) dispararon el nivel. Cuadro resumen
  arriba de la tabla ("X de Y personas presentan...") para que la alerta sea
  visible sin tener que leer la tabla entera.
- **Identidad visual**: paleta extraída del sitio real de GeoVictoria
  (`geovictoria.com/es-cl`, azul `#00AFF2` / ámbar `#FFBB00`, tipografía
  Nunito) — pero el **logo insertado en el encabezado
  (`Geovictoria/logo.jpg`) es el logo del CLIENTE, no de GeoVictoria** (el
  ícono es una casa con un enchufe, coherente con una empresa de energía/
  utilities, no con un software de control de asistencia). Por eso el
  subtítulo del reporte NO menciona "GeoVictoria" (18-ago-2026, corregido a
  pedido del usuario — "no debe hacer referencia al sistema que usamos", ya
  que GeoVictoria es solo la herramienta proveedora de los datos, el reporte
  es para/del cliente). Ojo si se retoca el header: no reintroducir el nombre
  del proveedor en texto visible.
- **Gráficos**: Chart.js (mismo `chart.umd.min.js` de
  `frontend/node_modules`, embebido inline) + `chartjs-plugin-datalabels`
  (también embebido desde `frontend/node_modules/chartjs-plugin-datalabels/dist/`,
  usado en el donut de permisos para mostrar % dentro de cada porción y en
  las barras de "Atrasos por área" para mostrar el valor dentro de la barra).
  "Evolución diaria" usa barras apiladas en vez de línea/área — con pocos
  días filtrados (ej. un solo "Día" seleccionado) una línea queda como un par
  de puntos sueltos casi invisibles, una barra apilada se centra sola sin
  importar cuántas categorías haya. "Atrasos por área" no tiene tope de
  cantidad (antes limitaba a un top 10) — el contenedor tiene alto fijo con
  scroll interno (~10 filas visibles) y el alto del canvas se ajusta
  dinámicamente según cuántas áreas tengan atrasos.

## Frontend

React + TypeScript + Vite (`frontend/`), inicializado con `npm create vite@latest -- --template react-ts`.
Decisiones tomadas con el usuario (13-ago-2026):

- **Sin librería de componentes**: CSS plano con variables (`frontend/src/styles/theme.css`).
  Nada de Tailwind/MUI.
- **Identidad visual "corporativa Chilquinta"** (el usuario la pidió como referencia de tono,
  no es la marca real del sistema — el nombre del sistema es "People Data & Automation").
  Paleta sacada del bundle JS real de chilquinta.cl (no hay logo propio, solo wordmark "PDA"):
  - Rojo primario `#da291c` (hover `#b5120b`, activo `#6e0b06`)
  - Navy/gris oscuro (sidebar/headers) `#2d3548`, `#373b53`, `#3b4559`
  - Grises claros de fondo `#f1f1f3`, `#f3f3f3`
  - Tipografía Montserrat (Google Fonts), bordes redondeados 10-16px, sombras suaves.
- **Roles**: solo existe el rol `administrador` por ahora. El menú lateral (`AppLayout.tsx`)
  tiene un único item "Dashboards" — sin lógica condicional por rol todavía.
- **Estructura**: `src/api/` (cliente fetch + JWT en localStorage, un archivo por dominio:
  `auth.ts`, `sobretiempo.ts`), `src/auth/` (`AuthContext`, `RequireAuth`), `src/components/layout/`
  (`AppLayout` = sidebar + topbar), `src/components/SearchableSelect.tsx` (select con buscador,
  un solo valor — hoy solo lo usa el filtro Mes) + `src/components/SearchableMultiSelect.tsx`
  (mismo estilo pero multi-selección, checkbox por opción, el menú no se cierra al elegir —
  usado por los otros 6 filtros de Sobretiempo, ver abajo). Tiene una prop opcional
  `permitirSeleccionarTodo` (17-ago-2026, a pedido del usuario, SOLO habilitada en el filtro
  Centro Costo — es el único con una lista larga donde tiene sentido) que agrega un item
  "Seleccionar los N filtrados" arriba de la lista cuando hay texto de búsqueda activo: un
  click agrega TODOS los resultados que matchean el texto a la selección (sin pisar lo ya
  elegido), y si ya estaban todos seleccionados el mismo item pasa a "Quitar los N filtrados".
  `src/pages/` (una página por ruta),
  `src/charts/registerCharts.ts` (registro central de Chart.js + paleta de charts, incluye
  `warning` ademas de `red`/`navy`/`success` para los badges de alerta/ritmo). Charting con
  `chart.js` + `react-chartjs-2` + `chartjs-plugin-datalabels` (valores/% sobre las barras,
  cargado por gráfico via el prop `plugins` de cada componente — nunca registrado global).
  `apiGet` (`src/api/client.ts`) manda arrays como parámetro repetido (`?x=A&x=B`), formato
  que espera FastAPI para listas en query params.
- `frontend/.env` tiene `VITE_API_BASE_URL` (default `http://localhost:8000`). CORS del backend
  ya permite cualquier origen (`allow_origins=["*"]`), no hace falta proxy de Vite.
- **`SobretiempoDashboardPage.tsx` — patrón de filtros y tablas, replicar para futuros dashboards**:
  - 7 filtros (Sociedad, Gerencia, Subgerencia, Unidad, Centro Costo, Concepto, Mes — Mes va al
    final, no al principio). **Todos multi-selección salvo Mes** (decisión del usuario,
    14-ago-2026): `SearchableMultiSelect` para los primeros 6, `SearchableSelect` solo para Mes.
    `Concepto` es un caso especial — sale del detalle transaccional (`Clasif Haber` del Excel,
    ver "Patrón de dashboards"), no existe en la tabla `resumen`, así que solo filtra los
    paneles transaccionales (¿En qué se gastó?, Ranking de Importe) y se calcula desde una
    fuente propia sin filtrar (`detalleCompleto`, fetched aparte de `opciones`).
    Filtros **en cascada**: las opciones de cada uno se recalculan client-side
    (`coincideConFiltros`/`coincideValor`, que aceptan tanto un string como un array — `FiltroValor`)
    a partir de un dataset base sin filtrar (`opciones`, fetched una sola vez),
    aplicando todos los DEMÁS filtros activos salvo el propio. Si una seleccion deja de ser
    valida al cambiar otro filtro, se saca del array (no se vacía todo) — `useEffect` por filtro.
  - Dos fetches paralelos por combinación de filtros: `resumen`/`detalle` (con TODOS los
    filtros incl. mes, para paneles de "foto de un mes") y `resumenAnual` (mismos filtros
    SIN mes, para paneles de tendencia anual tipo "Control Mensual" que necesitan los 12
    meses para sumar correctamente). Ver comentario en el `useEffect` principal.
  - **"Resumen"** (antes "Resumen Ejecutivo", renombrado 14-ago-2026): ya no tiene el selector
    de dimensión con gráfico de barras — es una sola barra de progreso horizontal de dos
    segmentos, rojo "Gastado" (crece) + verde "Disponible" (achica), cada uno con su texto
    centrado (se oculta si el segmento queda muy angosto, `< 8%`) — el color verde para
    "disponible" es a propósito, para que coincida con el título de la sección (la primera
    versión pintaba todo en rojo y confundía). Debajo, 4 datos: Gastado/Disponible/
    Presupuesto anual/Cuentas sin presupuesto, todo agregado sobre TODAS las cuentas en el
    alcance de los filtros de org, sin importar Mes.
  - **"Alerta"** (14-ago-2026, el cambio más grande de esta sesión): una sola tabla combinada
    con dos indicadores por cuenta (Sociedad+Ceco+Cuenta+Gerencia+Subgerencia+Unidad,
    dedupeada al mes más reciente disponible — cuidado, si no hay filtro de Mes esa dedup
    da Mes_Num=12 porque `resumen` trae el universo completo del año con meses futuros en $0,
    así que el mes de referencia real para "ritmo" usa `ultimoMesCerrado`, NO el Mes_Num de
    la fila):
    - **% Gastado**: `Pct_Ejecucion_Acumulado` tal cual lo manda el backend (Real acumulado /
      Presupuesto acumulado A LA FECHA) — umbral 50%/70%. Sube solo con el tiempo, sin
      importar el ritmo real, porque el presupuesto se suele cargar completo temprano en el
      año (en los datos 2026, para marzo/abril ya está el 100% cargado).
    - **Ritmo de gasto**: `(Real_Acumulado / Presupuesto_Anual_FIJO) / (mes_referencia / 12)`
      — 1.0 = exactamente a tiempo sin importar el mes, >1.0 = gastando más rápido de lo
      esperado. Mismo número que "proyección a fin de año / presupuesto anual". Umbral
      1.0x/1.3x. Se agregó específicamente porque "% Gastado" da falsos positivos crecientes
      a medida que avanza el año (no es lo mismo alertar en enero que en diciembre).
    - La tabla muestra la UNIÓN de ambos criterios (entra si cualquiera de los dos marca),
      para poder comparar cuenta por cuenta. Color de fila = el peor de los dos (`nivelCombinado`).
    - Sociedad se muestra como sigla (`siglaSociedad`, mapeo inverso del `SOCIEDAD_MAP` del
      backend) para no ensanchar la tabla — igual en la tabla "Detalle".
  - Tablas ("Detalle", "Alerta" y "Ranking de Importe") son **ordenables por columna** (un solo
    click invierte asc/desc) vía el helper genérico `ordenarFilas` + arrays de columnas tipados
    (`COLUMNAS_DETALLE`, `COLUMNAS_ALERTA`, `COLUMNAS_TRANSACCIONES`, interfaz `Columna<T>`) —
    agregar una columna nueva es agregar un objeto al array, no tocar el JSX de la tabla. Ambas
    muestran la lista COMPLETA (sin top-N) en un contenedor con scroll vertical + header sticky
    (`.sobretiempo__table-wrap--scroll` + `--rows20`/`--rows15`/`--rows10` según cuántas filas
    se quieren ver sin scrollear — Detalle 20, Ranking de Importe 15, Alerta 10).
  - **"Ranking de Importe" pasó de una fila por transacción a una fila por
    persona, con desglose por Concepto en columnas + columna Total**
    (17-ago-2026, en dos pasos). Bug original reportado por el usuario:
    "Carla Navarro" aparecía muchas veces en el ranking, incluso repetida
    con el mismo Concepto "Hora Extra" — porque `sobretiempo_detalle` es
    transaccional (un registro por persona+Concepto+MES, ver "Patrón de
    dashboards"), y a veces más de uno por mes si el mismo Concepto agrupa
    más de un Cuenta_Contable/Ceco (ej. "Horas Extras 50%" y "Horas Extras
    100%" son las dos Concepto="Hora Extra"); mostrar esas filas tal cual
    en un ranking fragmentaba a cada persona en N filas en vez de una. Un
    primer fix agregó por Cod_SAP+Concepto (una fila por persona+concepto),
    pero el usuario pidió ir más lejos: rankear por el Total de la persona,
    con el desglose por concepto como columnas adicionales en la MISMA fila
    (formato pivot) en vez de filas separadas. Diseño final en
    `SobretiempoDashboardPage.tsx`: `agregarPorPersona()` agrupa por
    `Cod_SAP` (no por `Nombre_Personal`, para no fusionar por error a dos
    personas distintas con el mismo nombre) y arma `PorConcepto: Record<string,
    number>` (Importe sumado por Concepto) + `Total`. `COLUMNAS_TRANSACCIONES`
    (tipo `Columna<PersonaImporte>[]`) arma sus columnas de Concepto a
    partir de la constante fija `CONCEPTOS_RANKING` (los 5 Concepto que
    existen hoy: Hora Extra, Turnos, Citación, Rot Horas Extra/Turnos, Bono
    Disponibilidad/Interluz/Alerta). Orden por defecto ahora es por "Total"
    descendente (antes por "Importe" de una transacción individual). La
    tabla quedó más ancha (hasta Nombre+Cargo+Gerencia+5 Concepto+Total = 9
    columnas) — ya andaba con scroll horizontal (`overflow-x: auto` en
    `.sobretiempo__table-wrap`), no hizo falta tocar CSS para eso.
    Dos ajustes de UX el mismo día: (1) "Rot Horas Extra/Turnos" y "Bono
    Disponibilidad/Interluz/Alerta" son Concepto con pocas personas pero
    nombres largos que ensanchaban la tabla sin aportar densidad de datos —
    quedaron con label acortado (`LABEL_CONCEPTO_CORTO`: "Rot HE/Turnos" y
    "Bono Disp.") y el nombre completo como tooltip nativo (`title` en el
    `<th>`, campo nuevo `titulo?` agregado a la interfaz genérica
    `Columna<T>` en `utils/tablas.ts`). (2) Una columna de Concepto en $0
    para TODAS las personas del alcance de filtros actual se oculta en vez
    de mostrarse vacía — `construirColumnasRanking()` pasó de ser una
    constante de módulo a una función, llamada desde un `useMemo`
    (`conceptosVisiblesRanking`) que filtra `CONCEPTOS_RANKING` contra
    `rankingImporte` antes de armar las columnas; esto es la postura
    contraria a la de otras columnas dinámicas del dashboard (ver "Concepto
    solo es válido para..." y los filtros en cascada más abajo), acá se
    prefirió ocultar por sobre mantener fijo, a pedido explícito del
    usuario.
  - **Header (título + los 7 filtros) fijo al hacer scroll** ("inmovilizar
    filas superiores" tipo Excel, 17-ago-2026, pedido del usuario):
    `.sobretiempo__header` en `SobretiempoDashboardPage.css` usa
    `position: sticky; top: 0` con fondo `--color-gray-bg` (mismo que el
    de la página, para que el contenido que pasa por debajo quede tapado)
    y un borde inferior para separarlo visualmente del resto al quedar
    pegado arriba.
    - **Bug encontrado y corregido en el mismo cambio**: en el HTML
      exportado standalone (sin login/routing, ver más abajo), `main.tsx`
      envolvía la página en `<div className="app-content">` — esa clase
      trae `overflow-y: auto` porque en el layout normal (`AppLayout`)
      vive dentro de un contenedor flex con altura acotada
      (`.app-main`/`.app-layout`, `min-height: 100vh`) y ahí SÍ hace
      scroll interno de verdad. Sin ese contexto de altura, el mismo
      `overflow-y: auto` igual convierte al div en "contenedor de scroll"
      a ojos del navegador (aunque nunca llegue a scrollear él solo,
      porque crece con su contenido) — y eso rompe `position: sticky` del
      header: deja de pegarse porque el sticky se calcula relativo a ESE
      contenedor, no al scroll real de la página. Se reprodujo visualmente
      con Chrome (MCP) sirviendo el HTML exportado por un `http.server` de
      Python en `Sobretiempo/data/reportes/` (los archivos exportados son
      autocontenidos, no necesitan el backend — ver "Reportes sin
      servidor"). Fix: en el branch exportado de `main.tsx`, el wrapper ya
      no reusa la clase `app-content` — pasa a un `<div style={{padding:
      "1.75rem"}}>` sin overflow, dejando el scroll real a cargo de
      html/body como corresponde en ese contexto standalone.
    - **Nota de la sesión**: el `http.server` de verificación se cortó
      solo a los segundos de levantarlo (mismo patrón que uvicorn, ver
      "Gotchas del entorno" — parece que el EDR mata cualquier
      `venv\Scripts\python.exe` que escuche en red, no solo FastAPI). No
      se pudo re-confirmar visualmente el fix después de aplicarlo, pero
      la causa raíz quedó identificada con certeza (se reprodujo el bug
      ANTES del fix, con capturas) y la solución es un cambio de CSS
      bien entendido, no una corrección especulativa.
  - **Botón "Descargar reporte (HTML)"** (`src/utils/exportarHtml.ts`): arma un HTML
    autocontenido reutilizando el MISMO bundle JS/CSS que la app en vivo (lo lee del propio
    `<script>`/`<link>` de la pagina, `document.querySelector('script[type="module"][src*="/assets/"]')`)
    + los datos completos embebidos (`window.__PDA_EXPORT__`) en vez de pedirlos a la API.
    `main.tsx` detecta esa variable global al cargar y renderiza `SobretiempoDashboardPage`
    sola (sin login/routing); la pagina detecta lo mismo y hace TODO el filtrado client-side
    contra los datos embebidos (mismo helper `coincideConFiltros` que usa para las opciones
    de los filtros). Por eso el archivo exportado conserva los 7 filtros funcionando
    offline. Solo funciona exportando desde el build de producción (necesita un
    `<script src="/assets/...">` real) — no desde el dev server de Vite.
  - **Botón "Actualizar datos (Excel)"** (solo rol `administrador`, prop `userRole` pasada
    desde un wrapper en `App.tsx` que sí puede usar `useAuth()` — el dashboard en sí no,
    porque también corre standalone en el HTML exportado sin `AuthProvider`): sube el Excel
    a `POST /dashboards/sobretiempo/actualizar` y despues bumpea un `refreshKey` en el
    `useEffect` de datos para refrescar el dashboard sin recargar la pagina.
- Probado end-to-end con Chrome (MCP) el 13-ago-2026, cuando los 7 filtros eran todos de
  selección única — login → `/dashboards` → `/dashboards/sobretiempo` con filtros en cascada,
  ordenamiento de tablas, scroll, y valores/% sobre los graficos → logout. Ojo: el screenshot
  de la herramienta a veces recorta el ancho real de la ventana (falso overflow) — si algo se
  ve "cortado" en una captura, confirmar con `getBoundingClientRect()`/`document.body.scrollWidth`
  via `javascript_tool` antes de asumir que es un bug real. **Los cambios del 14-ago-2026
  (multi-select, Alerta combinada, barra de Saldo disponible) se verificaron por otra vía**
  (`TestClient` de FastAPI en memoria + comparación manual contra SQL directo, ver "Estado
  actual") y NO se llegaron a probar clickeando en un Chrome real — el antivirus/EDR de esta
  sesión no dejó mantener un backend arriba el tiempo suficiente. Si se retoma el testing con
  Chrome, confirmar visualmente que el multi-select y la tabla de Alerta combinada se ven bien.

## Acceso en red (LAN/VPN)

Habilitado 13-ago-2026 para que otros usuarios se conecten desde la red interna
o VPN (nunca expuesto a Internet — sin port-forwarding en el router).

**Lo que ya está hecho (código):**

- **Backend sirve el frontend**: `backend/main.py` monta `frontend/dist`
  (build de producción, `vite build`) en el mismo puerto que la API — un
  catch-all `@app.get("/{full_path:path}")` devuelve `index.html` para
  cualquier ruta que no sea de la API ni un archivo estático, para que
  React Router maneje las rutas del lado del cliente (deep links y refresh
  funcionan). Este catch-all solo se activa si `frontend/dist/` existe — en
  desarrollo sin build, sigue funcionando el dev server de Vite en 5173
  aparte, sin conflicto.
- `frontend/.env.production` tiene `VITE_API_BASE_URL=` (vacío a propósito)
  para que en el build de producción las llamadas a la API sean same-origin
  (`/auth/login` en vez de `http://localhost:8000/auth/login`). El `.env`
  normal (dev) sigue apuntando a `http://localhost:8000`.
- **Límite de intentos de login**: `backend/auth/crud.py`
  (`MAX_INTENTOS_FALLIDOS = 5`, `BLOQUEO_MINUTOS = 15`). A los 5 intentos
  fallidos seguidos, la cuenta queda bloqueada 15 minutos (incluso con la
  contraseña correcta) — HTTP 429. Se resetea el contador en un login
  exitoso. Requirió migración de Alembic (`27395fc7fa19`,
  columnas `failed_login_attempts`/`locked_until` en `users`).
- Backend probado escuchando en `0.0.0.0:8000` (no solo `127.0.0.1`) —
  confirmado accesible por la IP de LAN de la notebook, no solo localhost.

**Para levantar en modo "producción" (LAN/VPN) en vez de dev:**

```powershell
cd frontend; node ".\node_modules\vite\bin\vite.js" build   # genera frontend/dist
cd ..
venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir backend
```

Con esto, un solo puerto (8000) sirve todo. Hay que repetir el `vite build`
cada vez que cambie el frontend (a diferencia del dev server, no hay hot
reload del lado del cliente en este modo).

**Pendiente — pasos manuales, no los ejecuta el agente (son cambios de
sistema/red, fuera del proyecto):**

1. **IP fija para la notebook**: hoy la IP de LAN (`192.168.1.132` al
   13-ago-2026, adaptador Wi-Fi) puede cambiar si se renueva el lease DHCP.
   Reservarla en el router (por MAC address) o configurar IP estática en
   Windows, para que el acceso de otros no se rompa solo.
2. **Regla de Firewall de Windows**, perfil **Privado** (no Público, para
   que no quede expuesto si la notebook se conecta a otra red):
   ```powershell
   New-NetFirewallRule -DisplayName "PDA (puerto 8000)" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
   ```
3. **Nombre `pda` en vez de la IP**: se descartó mDNS (`pda.local`) porque
   la mayoría de las VPN no reenvían tráfico multicast, así que no
   resolvería para quien se conecte por VPN. La alternativa 100% local (no
   sale de la red, no toca ningún DNS/hosting externo) es una línea en el
   archivo hosts de **cada máquina** que quiera usar el nombre corto —
   requiere permisos de administrador en esa máquina:
   - Windows: `C:\Windows\System32\drivers\etc\hosts`
   - Mac/Linux: `/etc/hosts`
   - Línea a agregar: `192.168.1.132   pda` (ajustar la IP si se reserva otra).
   - Con eso, `http://pda:8000` funciona igual que la IP. El puerto se
     mantiene (no se probó mover a 80/sin puerto, por riesgo de que algo más
     en Windows ya lo tenga reservado).
   - Esto hay que repetirlo en la máquina de cada usuario que quiera usar el
     nombre corto — no hay forma de resolverlo centralizado sin control
     sobre el DNS de la red (fuera del alcance de una notebook individual).

## Cómo correr el proyecto

**Forma normal: `Iniciar.bat`** (raíz del proyecto, doble click o
`.\Iniciar.bat` desde una terminal) — menú con Producción (compila el
frontend, levanta backend en `0.0.0.0:8000`, un solo puerto para toda la
red) o Desarrollo (backend en `127.0.0.1:8000` + frontend en `5173`,
ventanas separadas, con espera activa hasta confirmar que el backend
responde antes de mostrar los links). Es un `.bat` puro, no PowerShell —
así evita que una política de Execution Policy por GPO (común en Windows
Enterprise gestionado) bloquee un `.ps1`. Si de todos modos se cae solo a
los pocos segundos/minutos, ver el gotcha del antivirus/EDR más abajo — no
es un bug del script, es el entorno matando el proceso.

Para tocar el código directo (sin el menú), siempre desde la raíz del
proyecto (imports absolutos `backend.xxx`):

```powershell
# Instalar/actualizar dependencias
venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Levantar el backend
venv\Scripts\python.exe -m uvicorn backend.main:app --reload --reload-dir backend

# Migraciones
venv\Scripts\python.exe -m alembic revision --autogenerate -m "mensaje"
venv\Scripts\python.exe -m alembic upgrade head

# Crear un usuario administrador
venv\Scripts\python.exe -m backend.scripts.create_admin

# Levantar el frontend (puerto 5173) - "npm run dev" NO funciona, ver Gotchas ("&" en la ruta)
cd frontend; node ".\node_modules\vite\bin\vite.js"
```

## Gotchas del entorno (para no perder tiempo re-descubriéndolos)

- **Antivirus/EDR mata `venv\Scripts\python.exe` a los segundos/minutos de
  escuchar en red, sin traceback** — visto reiteradas veces el 14-ago-2026,
  con `--host 0.0.0.0` Y con `127.0.0.1` (no es por estar expuesto en red),
  y probado con background jobs, `Start-Process` desatachado, y hasta una
  Tarea Programada de Windows completamente independiente de la sesión —
  siempre el mismo patrón, `node.exe` nunca se ve afectado. Sintoma: la
  consola del backend vuelve a un prompt limpio sin ningún error, como si
  alguien hubiera hecho Ctrl+C. No se pudo confirmar 100% desde Windows
  Security (el usuario no ve alertas), pero el patrón es consistente con un
  EDR corporativo. Mitigación implementada: los scripts de
  "Reportes sin servidor" (ver esa sección) generan el reporte final sin
  abrir ningún puerto, así que no les pega este problema. Si hay que
  levantar el dashboard en vivo igual, `Iniciar.bat` ya tiene reintentos
  razonables pero no puede evitar que el proceso muera solo — es un
  problema de infraestructura/permisos de IT, no de código.
- **FastAPI + `@dataclass` con `Depends()`: un campo `Optional[list[str]] =
  None` NO se llena con query params repetidos**, siempre da `None` en
  silencio (sin error) aunque `?x=A&x=B` esté bien mandado — hace falta
  `Optional[list[str]] = Query(None)` explícito (import `Query` de
  `fastapi`). Un campo `Optional[str] = None` normal (sin lista) sí anda
  bien al lado sin el `Query()`. Se encontró armando el multi-select de
  filtros de Sobretiempo (`backend/dashboards/sobretiempo/router.py`,
  `SobretiempoFilters`) — verificado con un caso minimo aislado antes de
  aplicar el fix real.
- **`--reload` sin `--reload-dir backend` vigila TODO el proyecto, no solo el
  backend** (`Will watch for changes in these directories: ['D:\\People Data
  & Automation']`) — incluye `frontend/src`, `frontend/dist`, los `.db` de
  cada dashboard, `data/uploads/`, etc. Cualquier cambio ahí (editar un
  archivo del frontend, un `vite build`, o incluso una escritura normal a
  SQLite) dispara un reinicio completo del backend y corta la conexión de
  quien esté usando el dashboard en ese momento — sintoma: "cada vez que se
  edita algo, localhost se cae". Siempre levantar uvicorn con
  `--reload --reload-dir backend` (ya asi en `Iniciar.bat` y en los comandos
  de esta seccion) para que solo vigile el código que de verdad importa.
- **Si el backend corre SIN `--reload`, los cambios de código no se aplican** hasta
  reiniciar el proceso a mano — y el bug que produce es engañoso: los endpoints siguen
  respondiendo 200 con datos, así que parece un bug de lógica (ej. "el filtro no filtra")
  en vez de "el server tiene código viejo cargado". Ya pasó una vez con los filtros de
  Sobretiempo (agregué `sociedad`/`ceco`/`unidad`/etc. al router y el servidor de fondo
  seguia con la version vieja que solo soportaba `gerencia`). Siempre levantar el backend
  de desarrollo con `--reload` (ver "Cómo correr el proyecto"); si de todos modos un cambio
  de backend no se refleja al probarlo, sospechar primero del proceso viejo antes de
  buscar el bug en el código nuevo.
- **Variante del gotcha de arriba: si un `--reload` intenta recargar y el import falla**
  (ej. falta una dependencia nueva, como paso con `python-multipart` al agregar el upload
  de Sobretiempo), WatchFiles NO vuelve a intentar solo — el proceso viejo se queda
  respondiendo indefinidamente con las rutas de ANTES del cambio que rompio el import,
  sin ningun error visible salvo un `RuntimeError`/traceback que queda enterrado en el log
  de esa recarga puntual. Sintoma: un endpoint nuevo devuelve 404/405 aunque el codigo este
  bien y `python -c "from backend.main import app"` en un proceso nuevo funcione perfecto.
  Si eso pasa, revisar el log de la tarea de background buscando `WARNING: WatchFiles
  detected changes... Reloading` seguido de un traceback, y reiniciar el proceso entero
  (no alcanza con tocar un archivo para forzar otro reload si la causa ya esta resuelta,
  a veces hace falta el restart limpio).
- **pip install en batches grandes falla intermitentemente** en este entorno (procesos
  largos se cortan a mitad de descarga/instalación, exit code 43/1067). Solución: instalar
  en grupos chicos (4-5 paquetes top-level a la vez) en vez de todo `requirements.txt` junto.
- **`passlib` 1.7.4 no es compatible con `bcrypt>=4.1`** (bcrypt le sacó un atributo interno
  que passlib necesita). Por eso `requirements.txt` fija `bcrypt<4.1`. No actualizar bcrypt
  sin migrar de passlib a otra cosa.
- **`getpass` no funciona en terminales no interactivas de Windows** (falla feo, sin
  excepción catcheable). `create_admin.py` por eso usa `input()` visible en vez de
  `getpass`, con un flag `--password` para uso scripteado.
- **`email-validator` rechaza dominios reservados** (`.local`, `.test`, `.invalid`, etc. —
  RFC 2606). Usar dominios reales (aunque no resuelvan DNS) para emails de prueba.
- **Python del sistema es 3.14.7**, pero el proyecto usa **3.12.10** instalado aparte en
  `C:\Users\eoyarzun\Python312` (sin tocar el 3.14 ni el PATH global). El venv del proyecto
  ya quedó creado con esa versión — no recrear con `python` del PATH.
- **Nunca corro `git config` yo mismo** (restricción explícita del agente). Si hace falta
  configurar identidad de Git, pedírselo al usuario para que lo corra con `!`.
- **El "&" en "People Data & Automation" rompe `npm run <script>`, `npx` y cualquier
  binario de `node_modules\.bin\*.cmd` en Windows** (probado: `npm run dev`, `npm run build`,
  `npx tsc` fallan todos con `"...\node_modules\.bin\" no se reconoce como un comando`).
  cmd.exe interpreta el `&` de la ruta como separador de comandos al resolver esos shims
  `.cmd`, sin importar el quoting. Esto le pasa **también al usuario** si corre `npm run dev`
  en su propia terminal (cmd/PowerShell), no es un problema del agente. Workaround: invocar
  el entrypoint JS directo con `node`, ej. `node ".\node_modules\vite\bin\vite.js"` (dev/build)
  o `node ".\node_modules\typescript\bin\tsc" -b` (type-check), en vez de `npm run dev` /
  `npx vite` / `npx tsc`. No se investigó si hay un fix de config (ej. mover el proyecto a una
  ruta sin "&"); si el usuario ve el mismo error corriendo `npm run dev`, esa es la causa.

## Estructura

```
backend/        FastAPI: api, auth, database, dashboards, email, ai, reports, services
frontend/       React + TS + Vite, inicializado (ver seccion "Frontend")
assets/         Estaticos compartidos entre dashboards (ej. logo corporativo
                para encabezados de PDF), no especificos de ningun modulo
data/           sistema.db, reportes/, uploads/
Sobretiempo/    dashboard 1: normalizar_sobretiempo.py, generar_reporte_sobretiempo.py,
                Ejecutar.txt, data/ (db + backups/ + reportes/, todo gitignored)
Capacitacion/   dashboard 2: normalizar_capacitacion.py, generar_reporte_capacitacion.py,
                Ejecutar.txt, data/ (db + backups/ + reportes/, todo gitignored)
Geovictoria/    dashboard 3 (standalone, sin backend/DB): generar_reporte_asistencia.py,
                logo.jpg (logo del cliente, no de GeoVictoria), Archivos ejemplo/ y
                data/reportes/ gitignored
models/         referencias/config de modelos IA locales
onedrive_sync/  carpeta OneDrive sincronizada (se lee localmente, nunca via API)
docs/           documentacion
venv/           entorno virtual Python 3.12 (no versionado)
Iniciar.bat     menu Produccion/Desarrollo, ver "Como correr el proyecto"
```
