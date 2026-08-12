import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.auth.crud import get_user_by_email
from backend.auth.security import decode_access_token
from backend.database.db import get_db
from backend.database.models import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No se pudo validar la credencial",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if email is None:
            raise CREDENTIALS_ERROR
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR

    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR
    return user


def require_roles(*allowed_roles: UserRole):
    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta accion",
            )
        return user

    return _checker
