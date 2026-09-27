"""Declarative base and shared column conventions.

A naming convention is set on the metadata so every constraint gets a deterministic
name. Without it, PostgreSQL invents names for unnamed UNIQUE constraints and Alembic
autogenerate reports spurious drift on every run.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

#: Provider-tagged identity used for idempotent upserts and for swapping data
#: sources (rule R10), e.g. ``statsbomb:match:3943077``. Kept separate from the
#: surrogate ``id`` so a second provider can never collide with these rows.
SOURCE_PREFIX = "statsbomb"


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
