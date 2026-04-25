import os
from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from src.models import Persona, PersonaRun, Run  # noqa: F401

_DB_PATH = Path(os.getenv("DB_PATH", "szponciciel.db"))
_engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)


def get_engine():
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(_engine)


def get_session() -> Generator[Session, None, None]:
    with Session(_engine) as session:
        yield session
