import os
from collections.abc import Generator
from dotenv import load_dotenv

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from models import Persona, PersonaRun, Run  # noqa: F401

_engine: Engine | None = None

load_dotenv()


DEFAULT_DATABASE_URL = "sqlite:///szponciciel.db"


def database_url() -> str:
    """Resolve the SQLAlchemy URL.

    `DATABASE_URL` wins when set. Otherwise `RUN_MODE=test` selects an
    in-memory SQLite engine, and everything else falls back to the
    project's default on-disk SQLite file.
    """

    url = os.getenv("DATABASE_URL")
    if url:
        return url
    if os.getenv("RUN_MODE", "development") == "test":
        return "sqlite:///:memory:"
    return DEFAULT_DATABASE_URL


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url(),
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def reset_db() -> None:
    SQLModel.metadata.drop_all(get_engine())
    SQLModel.metadata.create_all(get_engine())


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
