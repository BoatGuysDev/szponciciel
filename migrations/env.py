import os
from logging.config import fileConfig
from pathlib import Path

import sqlmodel.sql.sqltypes
from alembic import context
from sqlmodel import SQLModel

import src.models  # noqa: F401

from src.db.database import get_engine
from src.logging_setup import setup_logging

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

setup_logging()

target_metadata = SQLModel.metadata


def _db_url() -> str:
    db_path = Path(os.getenv("DB_PATH", "szponciciel.db"))
    return f"sqlite:///{db_path}"


def _render_item(type_, obj, autogen_context):
    """Render SQLModel AutoString as plain sa.String() in migration files."""
    if type_ == "type" and isinstance(obj, sqlmodel.sql.sqltypes.AutoString):
        return "sa.String()"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=_render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
