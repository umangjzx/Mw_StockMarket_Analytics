"""
Alembic migration environment.

Configured for async SQLAlchemy (asyncpg) but uses the sync DSN for migrations
since Alembic doesn't natively support async engines. Models are auto-imported
via the models package __init__ so autogenerate sees all tables.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.db.base import Base

# Import all models so Alembic autogenerate picks up every table.
# Add new model files here as they are created.
from app.models import (  # noqa: F401
    channel,
    video,
    video_stat_snapshot,
    transcript,
    company,
    topic,
    summary,
    investment_thesis,
    sentiment,
    quote,
    key_number,
    actionable_insight,
    embedding,
    daily_report,
    user,
    task_log,
)

# Alembic Config object — provides access to values within alembic.ini
config = context.config

# Override sqlalchemy.url from our Pydantic settings (uses sync DSN)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SYNC)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL to stdout, no DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the DB and executes migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No pooling in migration runs
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
