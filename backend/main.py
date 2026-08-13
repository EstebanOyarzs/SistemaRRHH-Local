from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.auth.router import router as auth_router
from backend.config import PROJECT_ROOT, settings
from backend.dashboards.sobretiempo.router import router as sobretiempo_router

app = FastAPI(title=settings.app_name)

# Acceso solo desde la red local (LAN/VPN), sin exposicion a Internet.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


app.include_router(auth_router)
app.include_router(sobretiempo_router)

# Sirve el build de produccion del frontend (frontend/dist, generado con
# `vite build`) desde el mismo puerto que la API, para no tener que abrir
# dos puertos en el firewall ni mantener el dev server de Vite corriendo.
# En desarrollo (sin build) esto no se activa y se sigue usando el dev
# server de Vite en el puerto 5173 aparte.
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def servir_frontend(full_path: str):
        candidato = FRONTEND_DIST / full_path
        if full_path and candidato.is_file():
            return FileResponse(candidato)
        # Cualquier otra ruta (o una ruta de React Router como
        # /dashboards/sobretiempo) devuelve index.html y el router del
        # lado del cliente se encarga de mostrar la pantalla correcta.
        return FileResponse(FRONTEND_DIST / "index.html")
