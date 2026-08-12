# Sistema Web Local de Inteligencia Operacional

Sistema on-premise (notebook Windows) con dashboards interactivos, consultas IA locales,
generacion de informes, automatizacion de Outlook y autenticacion con Microsoft Entra ID.

Ejecuta completamente en red local, sin publicar servicios a Internet y sin depender
de servicios de IA pagados. Costo operativo: $0.

## Stack

- **Backend**: FastAPI + SQLAlchemy + Alembic + SQLite (Python 3.12)
- **Frontend**: React + TypeScript + Vite + Material UI + Apache ECharts + AG Grid
- **IA local**: LM Studio + Qwen 2.5 3B
- **Auth**: Microsoft Entra ID (MSAL)
- **Integracion M365**: Microsoft Graph API (Outlook, OneDrive)

## Estructura

```
backend/        API FastAPI (auth, dashboards, email, ai, reports, services)
frontend/       Aplicacion React
data/           Base SQLite, reportes generados, uploads
models/         Referencias/config de modelos IA locales
onedrive_sync/  Punto de lectura de la carpeta OneDrive sincronizada
docs/           Documentacion del proyecto
```

## Setup local

Ejecutar siempre desde la raiz del proyecto (los imports del backend son absolutos, `backend.xxx`).

```powershell
# Backend - instalar dependencias
venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Backend - levantar servidor de desarrollo
venv\Scripts\python.exe -m uvicorn backend.main:app --reload

# Frontend (proximamente)
cd frontend
npm install
npm run dev
```

Requiere Python 3.12 (venv en `/venv`, creado con `C:\Users\eoyarzun\Python312\python.exe -m venv venv`)
y Node.js (portable, agregado al PATH del usuario).
