import os
from collections.abc import Generator
from dotenv import load_dotenv

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

from models import Persona, PersonaRun, Run  # noqa: F401

_engine: Engine | None = None

load_dotenv()


def database_url() -> str:
    """Resolve the SQLAlchemy URL from `DATABASE_URL`.

    Required — there is no implicit default. The test suite pins this to
    `sqlite:///:memory:` via `src/tests/conftest.py`, so production code
    stays free of test-aware branching.
    """

    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env or export it "
            "in your environment."
        )
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url(),
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def reset_engine() -> None:
    """Drop the cached engine. Used by test setup and rare reload scenarios."""

    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def reset_db() -> None:
    SQLModel.metadata.drop_all(get_engine())
    SQLModel.metadata.create_all(get_engine())


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
