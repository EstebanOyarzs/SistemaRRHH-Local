"""Bootstrap del primer usuario Administrador.

Uso (desde la raiz del proyecto, con el venv activo):
    python -m backend.scripts.create_admin
"""

import argparse
import sys

from backend.auth import crud
from backend.database.db import SessionLocal
from backend.database.models import UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description="Crear un usuario Administrador")
    parser.add_argument("--email", help="Email del usuario")
    parser.add_argument("--full-name", help="Nombre completo")
    parser.add_argument(
        "--role",
        choices=[r.value for r in UserRole],
        default=UserRole.ADMINISTRADOR.value,
        help="Rol a asignar (default: administrador)",
    )
    parser.add_argument(
        "--password",
        help="Contraseña (evita el prompt interactivo; util para uso scripteado)",
    )
    args = parser.parse_args()

    email = args.email or input("Email: ").strip()
    full_name = args.full_name or input("Nombre completo: ").strip()

    if args.password:
        password = args.password
    else:
        # getpass requiere consola real y no funciona en terminales no interactivas
        # (pipes), por lo que se usa input() visible como entrada estandar.
        password = input("Contraseña: ")
        password_confirm = input("Confirmar contraseña: ")
        if password != password_confirm:
            print("Las contraseñas no coinciden.", file=sys.stderr)
            sys.exit(1)
    if len(password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        if crud.get_user_by_email(db, email):
            print(f"Ya existe un usuario con el email {email}.", file=sys.stderr)
            sys.exit(1)

        user = crud.create_user(
            db,
            email=email,
            full_name=full_name,
            password=password,
            role=UserRole(args.role),
        )
        print(f"Usuario creado: {user.email} ({user.role.value})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
