"""
SQLAlchemy declarative base and naming conventions.

All ORM models should inherit from `Base`. The naming conventions ensure that
Alembic autogenerate produces consistent constraint names across migrations.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Explicit naming conventions so Alembic autogenerate produces deterministic names.
# Without this, PostgreSQL generates constraint names like 'fk_1234567890' that differ
# between environments and make migration diffs noisy.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
