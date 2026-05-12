from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from config import settings
from models import Persona, PersonaRun, Run  # noqa: F401

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        if settings.run_mode == "test":
            db_path = Path(":memory:")
        else:
            db_path = settings.db_path

        _engine = create_engine(
            f"sqlite:///{db_path}",
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
