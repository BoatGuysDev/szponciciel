from logging.config import fileConfig

import sqlmodel.sql.sqltypes
from alembic import context
from sqlmodel import SQLModel

import models  # noqa: F401

from db.database import database_url, get_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _render_item(type_, obj, autogen_context):
    """Render SQLModel AutoString as plain sa.String() in migration files."""
    if type_ == "type" and isinstance(obj, sqlmodel.sql.sqltypes.AutoString):
        return "sa.String()"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
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
