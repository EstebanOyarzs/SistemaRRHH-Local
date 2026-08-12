import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
ENV_FILE = PROJECT_ROOT / ".env"


def _ensure_jwt_secret() -> None:
    """Genera y persiste una JWT_SECRET_KEY local si todavia no existe.

    Evita que el sistema dependa de que el usuario genere el secreto a mano;
    se guarda en .env (nunca versionado) para que las sesiones sobrevivan reinicios.
    """
    if ENV_FILE.exists() and "JWT_SECRET_KEY=" in ENV_FILE.read_text(encoding="utf-8"):
        return
    secret = secrets.token_hex(32)
    with ENV_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\nJWT_SECRET_KEY={secret}\n")


_ensure_jwt_secret()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Sistema Web Local de Inteligencia Operacional"
    environment: str = "development"

    database_path: Path = DATA_DIR / "sistema.db"

    # Autenticacion interna (usuarios/roles en SQLite, sin Entra ID)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # jornada laboral

    # LM Studio (IA local)
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "qwen2.5-3b-instruct"

    # OneDrive sincronizado localmente
    onedrive_sync_path: Path = PROJECT_ROOT / "onedrive_sync"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


settings = Settings()
