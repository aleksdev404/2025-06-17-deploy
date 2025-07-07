# backend/app/manage.py

import typer
from database import SessionLocal
from models import User, Role
from security import hash_password
from datetime import datetime
import uuid

cli = typer.Typer()


@cli.command()
def create_admin(
    username: str = typer.Option("admin", "--username", "-u", help="Username"),
    password: str = typer.Option("admin123", "--password", "-p", help="Password")
):
    """Создание администратора"""
    db = SessionLocal()
    if db.query(User).filter_by(username=username).first():
        typer.echo(f"❗ Пользователь '{username}' уже существует")
        return

    user = User(
        id=uuid.uuid4(),
        username=username,
        hashed_password=hash_password(password),
        role=Role.admin,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.close()
    typer.echo(f"✅ Пользователь '{username}' успешно создан")


if __name__ == "__main__":
    cli()
