from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth.router import router as auth_router
from backend.config import settings

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
