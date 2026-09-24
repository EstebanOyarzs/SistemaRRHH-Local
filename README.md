# Sistema Web Local de Inteligencia Operacional

Sistema de dashboards e informes de RRHH, pensado on-premise (notebook Windows) para
dos formas de uso:

- **Extraccion local de reportes**: scripts que leen un Excel y generan un HTML
  autocontenido (datos + graficos embebidos), sin servidor ni instalacion — se abre
  directo en el navegador. Asi funcionan hoy Sobretiempo, Capacitacion, Control de
  Asistencia y Viaticos.
- **Montado como servidor**: el mismo sistema corre en la red local (LAN/VPN) con
  login, roles/privilegios y vistas por usuario (autenticacion interna propia, sin
  depender de Microsoft Entra ID ni de ningun proveedor externo de identidad).

No hay costos operativos ni dependencia de servicios de IA pagados por ahora, pero
la arquitectura no lo impide — puede sumarse una API de IA de pago mas adelante si
hace falta mas capacidad que la de un modelo local.

## Stack

- **Backend**: FastAPI + SQLAlchemy + Alembic + SQLite (Python 3.12)
- **Frontend**: React + TypeScript + Vite + Material UI + Apache ECharts + AG Grid
- **Auth**: interna (usuario/clave en SQLite, JWT + bcrypt, roles) — no depende de
  Microsoft Entra ID ni de ningun proveedor externo
- **IA**: en evaluacion (LM Studio + modelo local, o una API paga si hace falta mas
  capacidad) — todavia no implementado
- **Outlook**: automatizacion del Outlook de escritorio via COM/pywin32 (no requiere
  Microsoft Graph) — todavia no implementado
- **OneDrive**: lectura de la carpeta sincronizada localmente (`onedrive_sync/`), sin
  API externa

## Estructura

```
backend/                API FastAPI (auth, dashboards, email, ai, reports, services)
frontend/               Aplicacion React (dashboards montados como servidor, con login)
data/                   Base SQLite, reportes generados, uploads
Sobretiempo/            Dashboard standalone: normalizar + generar reporte HTML
Capacitacion/           Dashboard standalone: normalizar + generar reporte Excel
Control de Asistencia/  Dashboard standalone: generar reporte HTML (GeoVictoria)
Viaticos/               Dashboard standalone: normalizar + generar reporte HTML
models/                 Referencias/config de modelos IA locales
onedrive_sync/          Punto de lectura de la carpeta OneDrive sincronizada
docs/                   Documentacion del proyecto
```

Cada dashboard standalone (Sobretiempo, Capacitacion, Control de Asistencia,
Viaticos) tiene su propio Excel de origen y reportes generados, todos excluidos
del repositorio por contener datos personales reales (RUT, nombres) — ver
`.gitignore`.

## Setup local

Ejecutar siempre desde la raiz del proyecto (los imports del backend son absolutos, `backend.xxx`).

```powershell
# Backend - instalar dependencias
venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Backend - levantar servidor de desarrollo
venv\Scripts\python.exe -m uvicorn backend.main:app --reload --reload-dir backend

# Frontend (proximamente)
cd frontend
npm install
npm run dev
```

Requiere Python 3.12 (venv en `/venv`, creado con `C:\Users\eoyarzun\Python312\python.exe -m venv venv`)
y Node.js (portable, agregado al PATH del usuario).
