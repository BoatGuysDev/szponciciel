import os
from collections.abc import Generator
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from src.models import Persona, PersonaRun, Run  # noqa: F401

_engine: Engine | None = None

load_dotenv()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        run_mode = os.getenv("RUN_MODE", "development")
        if run_mode == "test":
            db_path = ""
        else:
            db_path = Path("/", os.getenv("DB_PATH", "szponciciel.db"))

        _engine = create_engine(
            f"sqlite://{db_path}",
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
