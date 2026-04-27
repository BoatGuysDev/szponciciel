import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

from src.models import Persona, PersonaRun, Run  # noqa: F401

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        db_path = Path(os.getenv("DB_PATH", "szponciciel.db"))
        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_test_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    return engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
