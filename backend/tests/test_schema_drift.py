"""The models in app/models are a mapping of the designed schema (db/, generated from
docs/database/schema_spec.py). They never create tables. This test fails when they drift apart."""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

from app.models import Base
from app.models import enums as model_enums

# SQLAlchemy type -> PostgreSQL udt_name
UDT = [
    (pg.CITEXT, "citext"), (pg.UUID, "uuid"), (pg.JSONB, "jsonb"), (pg.INET, "inet"),
    (pg.TSVECTOR, "tsvector"), (pg.NUMRANGE, "numrange"), (pg.REAL, "float4"),
    (sa.Text, "text"), (sa.Boolean, "bool"), (sa.SmallInteger, "int2"), (sa.BigInteger, "int8"),
    (sa.Integer, "int4"), (sa.Numeric, "numeric"), (sa.DateTime, "timestamptz"), (sa.Date, "date"),
    (sa.Interval, "interval"), (sa.LargeBinary, "bytea"), (sa.CHAR, "bpchar"), (Vector, "vector"),
]  # fmt: skip


# In the database on purpose and not application tables: a view, PostGIS's catalogue, dbmate's log.
NOT_MAPPED = {"community_feed", "geography_columns", "geometry_columns", "spatial_ref_sys",
              "schema_migrations"}


def expected_udt(column: sa.Column) -> str:
    t = column.type
    if isinstance(t, sa.Enum):
        return t.name
    if isinstance(t, pg.ARRAY):
        return "_" + expected_udt(sa.Column("x", t.item_type))
    for cls, udt in UDT:
        if isinstance(t, cls):
            return udt
    return type(t).__name__


async def find_drift(conn) -> list[str]:
    problems: list[str] = []
    rows = (await conn.execute(sa.text(
        "select table_name, column_name, is_nullable = 'YES', column_default is not null, "
        "       udt_name, is_generated = 'ALWAYS' "
        "from information_schema.columns where table_schema = 'public'"))).all()
    live: dict[str, dict[str, tuple]] = {}
    for table, column, nullable, has_default, udt, generated in rows:
        live.setdefault(table, {})[column] = (nullable, has_default, udt, generated)

    for table in Base.metadata.sorted_tables:
        if table.name not in live:
            problems.append(f"{table.name}: table is not in the database")
            continue
        db_cols = live[table.name]
        model_cols = {c.name: c for c in table.columns}
        for name in sorted(set(db_cols) - set(model_cols)):
            if not db_cols[name][3]:  # generated columns need no mapping
                problems.append(f"{table.name}.{name}: in the database, not in the model")
        for name in sorted(set(model_cols) - set(db_cols)):
            problems.append(f"{table.name}.{name}: in the model, not in the database")
        for name in sorted(set(model_cols) & set(db_cols)):
            nullable, has_default, udt, generated = db_cols[name]
            column = model_cols[name]
            if generated and column.server_default is None:
                problems.append(f"{table.name}.{name}: generated there, writable here")
            if generated:
                continue
            if expected_udt(column) != udt:
                problems.append(
                    f"{table.name}.{name}: type {expected_udt(column)} here, {udt} there")
            if column.nullable != nullable:
                problems.append(
                    f"{table.name}.{name}: nullable={column.nullable} here, {nullable} there")
            # The ORM sends an explicit NULL for a column it thinks has no default.
            mapped_default = column.server_default is not None or column.default is not None
            if has_default and not nullable and not mapped_default and not column.primary_key:
                problems.append(f"{table.name}.{name}: database default not declared in the model")
            # ...and omits a column it thinks the database will fill in.
            if column.server_default is not None and not has_default and not nullable:
                problems.append(f"{table.name}.{name}: model declares a default the database lacks")
            literal = getattr(column.server_default, "arg", None)
            if isinstance(column.type, sa.Enum) and isinstance(literal, str) \
                    and literal not in column.type.enums:
                problems.append(
                    f"{table.name}.{name}: default {literal!r} is not a {column.type.name}")

    mapped = {t.name for t in Base.metadata.tables.values()}
    for name in sorted(set(live) - mapped - NOT_MAPPED):
        # Partitions of mapped tables are not tables of their own.
        if not any(name.startswith(parent + "_") for parent in mapped):
            problems.append(f"{name}: table is in the database, not in the models")

    live_enums: dict[str, list[str]] = {}
    for name, label in (await conn.execute(sa.text(
            "select t.typname, e.enumlabel from pg_enum e join pg_type t on t.oid = e.enumtypid "
            "order by t.typname, e.enumsortorder"))).all():
        live_enums.setdefault(name, []).append(label)
    mine = {v.name: list(v.enums) for v in vars(model_enums).values() if isinstance(v, sa.Enum)}
    for name in sorted(set(live_enums) | set(mine)):
        if live_enums.get(name) != mine.get(name):
            problems.append(f"enum {name}: {mine.get(name)} here, {live_enums.get(name)} there")
    return problems


async def test_models_match_the_designed_schema(db):
    problems = await find_drift(await db.connection())
    assert not problems, "\n".join(problems)
