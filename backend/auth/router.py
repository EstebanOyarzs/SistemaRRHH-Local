from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.crud import authenticate_user
from backend.auth.dependencies import get_current_user, require_roles
from backend.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserOut
from backend.auth.security import create_access_token
from backend.auth import crud
from backend.database.db import get_db
from backend.database.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    existente = crud.get_user_by_email(db, payload.email)
    if existente and crud.esta_bloqueado(existente):
        minutos = crud.minutos_restantes_bloqueo(existente)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos fallidos. Volve a intentar en {minutos} minuto(s).",
        )

    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        if existente:
            crud.registrar_intento_fallido(db, existente)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    crud.registrar_login_exitoso(db, user)
    token = create_access_token(subject=user.email, role=user.role.value)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(UserRole.ADMINISTRADOR)),
):
    if crud.get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya esta registrado")
    return crud.create_user(db, payload.email, payload.full_name, payload.password, payload.role)
