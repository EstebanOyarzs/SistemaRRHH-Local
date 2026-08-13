from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.auth.security import hash_password, verify_password
from backend.database.models import User, UserRole

MAX_INTENTOS_FALLIDOS = 5
BLOQUEO_MINUTOS = 15


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def esta_bloqueado(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > datetime.utcnow()


def minutos_restantes_bloqueo(user: User) -> int:
    if not user.locked_until:
        return 0
    restante = (user.locked_until - datetime.utcnow()).total_seconds()
    return max(1, int(restante // 60) + 1)


def registrar_intento_fallido(db: Session, user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_INTENTOS_FALLIDOS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=BLOQUEO_MINUTOS)
        user.failed_login_attempts = 0
    db.commit()


def registrar_login_exitoso(db: Session, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()


def create_user(db: Session, email: str, full_name: str, password: str, role: UserRole) -> User:
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
