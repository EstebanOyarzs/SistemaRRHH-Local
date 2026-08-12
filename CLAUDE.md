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

Pendiente (orden sugerido, ver spec original del usuario para el detalle de cada módulo):
1. Repo Git — **bloqueado**: falta configurar `git config user.name` / `user.email`
   (no lo hago yo mismo, ver más abajo) y crear el repo privado en GitHub.
2. Módulo de dashboards (backend/dashboards/ + frontend React aún no inicializado).
3. Integración LM Studio (Qwen 2.5 3B) para consultas IA e informes.
4. Automatización Outlook vía pywin32/COM (backend/email/).
5. Generación de reportes Excel/Word/PDF (backend/reports/).
6. Frontend: aún no se corrió `npm create vite`. Node portable está en
   `C:\Users\eoyarzun\node-v24.19.0-win-x64`, ya agregado al PATH de usuario.

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
```

## Gotchas del entorno (para no perder tiempo re-descubriéndolos)

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

## Estructura

```
backend/        FastAPI: api, auth, database, dashboards, email, ai, reports, services
frontend/       React (sin inicializar todavia)
data/           sistema.db, reportes/, uploads/
models/         referencias/config de modelos IA locales
onedrive_sync/  carpeta OneDrive sincronizada (se lee localmente, nunca via API)
docs/           documentacion
venv/           entorno virtual Python 3.12 (no versionado)
```
