"""Declarative base and the column helpers every model file uses."""

from typing import Any

from sqlalchemy import DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Titan Multimodal Embeddings G1 output size (technical documentation 7.2).
VECTOR_DIM = 1024


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def pk() -> Any:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def fk(target: str, *, nullable: bool = False, primary_key: bool = False, index: bool = True,
       use_alter: bool = False, **kw: Any) -> Any:
    """Foreign key column. `use_alter` breaks the cycles the ERD contains."""
    ref = ForeignKey(target, use_alter=use_alter)
    if target.endswith(".code"):
        from sqlalchemy import Text
        return mapped_column(Text, ref, nullable=nullable, primary_key=primary_key,
                             index=index and not primary_key, **kw)
    return mapped_column(UUID(as_uuid=True), ref, nullable=nullable, primary_key=primary_key,
                         index=index and not primary_key, **kw)


def ts(*, nullable: bool = True, now: bool = False, **kw: Any) -> Any:
    return mapped_column(DateTime(timezone=True), nullable=nullable,
                         server_default=func.now() if now else None, **kw)


def created() -> Any:
    return ts(nullable=False, now=True)


def updated() -> Any:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                         onupdate=func.now())
