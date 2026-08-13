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

Pendiente (orden sugerido, ver spec original del usuario para el detalle de cada módulo):
1. Más planillas/dashboards siguiendo el mismo patrón que Sobretiempo (ver abajo),
   agregando su card en `frontend/src/pages/DashboardsHomePage.tsx` y su ruta/pagina.
2. Integración LM Studio (Qwen 2.5 3B) para consultas IA e informes.
3. Automatización Outlook vía pywin32/COM (backend/email/).
4. Generación de reportes Excel/Word/PDF (backend/reports/).
5. Roles: por ahora solo se usa el rol `administrador` (decision del usuario,
   13-ago-2026). El sidebar/menu no tiene lógica condicional por rol todavía;
   cuando haya perfiles no-admin, hay que agregarla en `AppLayout.tsx`.

## Patrón de dashboards (establecido con Sobretiempo, replicar para los que sigan)

Cada dashboard es una planilla mensual que se normaliza y se carga a SQLite.
Para Sobretiempo (control de horas extra vs. presupuesto) quedó así:

- **`Sobretiempo/`** (carpeta en la raíz del proyecto, junto a `backend/` y
  `frontend/`): solo el ETL. `normalizar_sobretiempo.py` lee el Excel bruto
  mensual ("Control de Sobretiempo 2026.xlsx", hojas `DETALLE 2,0` y
  `PPTO 2026`) y carga 4 tablas a una SQLite propia
  (`Sobretiempo/data/sobretiempo.db`), reemplazándolas por completo en cada
  corrida (el Excel de origen ya trae el acumulado del año, no hace falta
  mergear). Uso mensual:
  `venv\Scripts\python.exe Sobretiempo\normalizar_sobretiempo.py "ruta\archivo.xlsx"`.
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
  + constantes de nombre de tabla), `schemas.py` (Pydantic, un modelo por
  tabla con todas las columnas) y `router.py` (4 endpoints GET, uno por
  tabla, con filtros opcionales `anio`/`mes`/`sociedad`/`gerencia`/
  `subgerencia`/`unidad`/`ceco`/`cuenta`, protegidos con `get_current_user`
  — cualquier rol autenticado puede leer). `TABLE_COLUMNS` en `router.py`
  define qué filtros aplican a cada tabla (`sobretiempo_resumen_gerencia`
  solo tiene Gerencia+Subgerencia+Mes, así que ahí se ignoran silenciosamente
  los filtros que no le aplican en vez de romper el SQL). Montado en
  `backend/main.py` bajo `/dashboards/sobretiempo/...`.
- El HTML de ejemplo (`Sobretiempo_Dashboard.html`, Chart.js con los datos
  embebidos) mapea 1 a 1 con las 4 tablas: `resumenGerencia` → panel
  "Resumen Ejecutivo", `resumen` → paneles "Control Mensual" y "Detalle por
  Responsable", `detalle` → panel "¿En qué se gastó?". Sirve de referencia
  para qué campos va a necesitar el futuro frontend.

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
  reusado en los 7 filtros), `src/pages/` (una página por ruta), `src/charts/registerCharts.ts`
  (registro central de Chart.js + paleta de charts). Charting con `chart.js` + `react-chartjs-2`
  + `chartjs-plugin-datalabels` (valores/% sobre las barras y el donut, cargado por gráfico via
  el prop `plugins` de cada componente — nunca registrado global, para no afectar otros charts).
- `frontend/.env` tiene `VITE_API_BASE_URL` (default `http://localhost:8000`). CORS del backend
  ya permite cualquier origen (`allow_origins=["*"]`), no hace falta proxy de Vite.
- **`SobretiempoDashboardPage.tsx` — patrón de filtros y tablas, replicar para futuros dashboards**:
  - 7 filtros (Mes, Sociedad, Gerencia, Subgerencia, Unidad, Centro Costo, Cuenta) con
    `SearchableSelect`, **en cascada**: las opciones de cada uno se recalculan client-side
    (`rowMatches`) a partir de un dataset base sin filtrar (`opciones`, fetched una sola vez),
    aplicando todos los DEMÁS filtros activos salvo el propio — evita que un filtro se
    autoborre sus propias opciones. Si una seleccion deja de ser valida al cambiar otro
    filtro, se limpia sola (`useEffect` por filtro).
  - Dos fetches paralelos por combinación de filtros: `resumen`/`detalle` (con TODOS los
    filtros incl. mes, para paneles de "foto de un mes") y `resumenAnual` (mismos filtros
    SIN mes, para paneles de tendencia anual tipo "Control Mensual" que necesitan los 12
    meses para sumar correctamente). Ver comentario en el `useEffect` principal.
  - "Resumen Ejecutivo" ya NO usa la tabla `resumen_gerencia` (esa solo soporta filtro por
    Gerencia/Subgerencia) — se recalcula client-side desde `resumenAnual`, replicando
    exactamente la metodología original (`Con_Presupuesto_Asignado` filtrado antes de sumar,
    ver `resumenAnualPresupuestado`) para que las cifras no cambien, pero ahora respeta los
    7 filtros. Tiene un selector de 5 dimensiones (Sociedad/Gerencia/Subgerencia/Unidad/Cuenta,
    círculos tipo radio, default Sociedad) que reagrupa el gráfico de saldo en el momento.
  - Tablas ("Detalle" y "Ranking de Importe") son **ordenables por columna** (un solo click
    invierte asc/desc) vía el helper genérico `ordenarFilas` + arrays de columnas tipados
    (`COLUMNAS_DETALLE`, `COLUMNAS_TRANSACCIONES`, interfaz `Columna<T>`) — agregar una
    columna nueva es agregar un objeto al array, no tocar el JSX de la tabla. Ambas muestran
    la lista COMPLETA (sin top-N) en un contenedor con scroll vertical + header sticky
    (`.sobretiempo__table-wrap--scroll` + `--rows15`/`--rows10` según cuántas filas se
    quieren ver sin scrollear).
- Probado end-to-end con Chrome (MCP): login → `/dashboards` → `/dashboards/sobretiempo` con
  los 7 filtros en cascada, ordenamiento de tablas, scroll, y valores/% sobre los graficos →
  logout. Ojo: el screenshot de la herramienta a veces recorta el ancho real de la ventana
  (falso overflow) — si algo se ve "cortado" en una captura, confirmar con
  `getBoundingClientRect()`/`document.body.scrollWidth` via `javascript_tool` antes de asumir
  que es un bug real.

## Cómo correr el proyecto

Siempre desde la raíz del proyecto (imports absolutos `backend.xxx`):

```powershell
# Instalar/actualizar dependencias
venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Levantar el backend
venv\Scripts\python.exe -m uvicorn backend.main:app --reload

# Migraciones
venv\Scripts\python.exe -m alembic revision --autogenerate -m "mensaje"
venv\Scripts\python.exe -m alembic upgrade head

# Crear un usuario administrador
venv\Scripts\python.exe -m backend.scripts.create_admin

# Levantar el frontend (puerto 5173) - "npm run dev" NO funciona, ver Gotchas ("&" en la ruta)
cd frontend; node ".\node_modules\vite\bin\vite.js"
```

## Gotchas del entorno (para no perder tiempo re-descubriéndolos)

- **Si el backend corre SIN `--reload`, los cambios de código no se aplican** hasta
  reiniciar el proceso a mano — y el bug que produce es engañoso: los endpoints siguen
  respondiendo 200 con datos, así que parece un bug de lógica (ej. "el filtro no filtra")
  en vez de "el server tiene código viejo cargado". Ya pasó una vez con los filtros de
  Sobretiempo (agregué `sociedad`/`ceco`/`unidad`/etc. al router y el servidor de fondo
  seguia con la version vieja que solo soportaba `gerencia`). Siempre levantar el backend
  de desarrollo con `--reload` (ver "Cómo correr el proyecto"); si de todos modos un cambio
  de backend no se refleja al probarlo, sospechar primero del proceso viejo antes de
  buscar el bug en el código nuevo.
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
data/           sistema.db, reportes/, uploads/
models/         referencias/config de modelos IA locales
onedrive_sync/  carpeta OneDrive sincronizada (se lee localmente, nunca via API)
docs/           documentacion
venv/           entorno virtual Python 3.12 (no versionado)
```
