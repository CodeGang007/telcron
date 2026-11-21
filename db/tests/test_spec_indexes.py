"""Every index in docs/database/schema_spec.py is the index the migrated database has, and no foreign key
is left without an index that serves it, except the ones listed here (DEF-080).

An index added after its phase was applied (`I(..., since=<migration>)`) is written into its own
generated migration; its down-step drops it and nothing else.
"""
import psycopg
import pytest

from conftest import ROOT, one, up_part
from test_spec_checks import BUILD, SPEC


def spec_indexes(db):
    """{index name: definition} for every `I(...)` in the spec, deparsed by PostgreSQL on an empty copy."""
    out = {}
    for t in SPEC.TABLES:
        for n, ix in enumerate(t.indexes, 1):
            name = BUILD.index_name(t, n)
            with db.transaction(force_rollback=True):
                db.execute(f"CREATE TEMP TABLE spec_probe (LIKE {t.name})")
                ddl = BUILD.create_index(t, n, ix).replace(f" {name} ON {t.name} ", " probe ON spec_probe ", 1)
                db.execute(ddl)
                d = one(db, "SELECT pg_get_indexdef('pg_temp.probe'::regclass)")
            out[name] = d.split(" USING ", 1)[1]
    return out


def live_indexes(db):
    rows = db.execute("""
        SELECT c.relname, pg_get_indexdef(c.oid) FROM pg_class c JOIN pg_index i ON i.indexrelid = c.oid
          JOIN pg_class r ON r.oid = i.indrelid
         WHERE c.relnamespace = 'public'::regnamespace AND c.relname ~ '_i[0-9]+_idx$' AND NOT r.relispartition""").fetchall()
    return {name: d.split(" USING ", 1)[1] for name, d in rows}


def test_every_index_in_the_spec_is_the_index_the_database_has(db):
    spec, live = spec_indexes(db), live_indexes(db)
    assert sorted(set(spec) - set(live)) == [], "in the spec, missing from the database"
    assert sorted(set(live) - set(spec)) == [], "in the database, missing from the spec"
    assert {k: (spec[k], live[k]) for k in spec if spec[k] != live[k]} == {}, "spec (left) and database (right) disagree"


def test_the_brand_index_serves_a_brands_products_in_name_order(db):
    assert "(brand_id, canonical_name, id)" in live_indexes(db)["products_i4_idx"]


LATER = sorted({ix.since for t in SPEC.TABLES for ix in t.indexes if ix.since})


@pytest.mark.parametrize("fname", LATER)
def test_a_later_index_migration_is_generated_and_its_down_step_drops_only_its_indexes(db, fname):
    text = (ROOT / "db" / "migrations" / fname).read_text()
    assert text == BUILD.later_index_migrations()[fname], "edited by hand or stale: run `make db-gen`"
    before = live_indexes(db)
    names = [BUILD.index_name(t, n) for t in SPEC.TABLES for n, ix in enumerate(t.indexes, 1) if ix.since == fname]
    db.execute(text.split("-- migrate:down", 1)[1])
    after = live_indexes(db)
    assert set(before) - set(after) == set(names)
    db.execute(up_part(text))
    assert live_indexes(db) == before


def test_a_later_index_is_left_out_of_its_frozen_phase_migration():
    phase1 = (ROOT / "db" / "migrations" / BUILD.PHASE_FILES[1]).read_text()
    assert "products_i4_idx" not in phase1 and "brand_id, canonical_name" not in phase1


# Foreign keys whose child rows no index can find (the lookup a parent's DELETE or key change does).
# Each was checked on 2026-11-22: its parent is never deleted, or only rarely, so the scan is acceptable for
# now. A new foreign key without an index fails the test below: give it one in the spec, or add it here
# with the reason.
UNINDEXED_FKS = {
    ("coin_ledger_entries", "reverses_entry_id"),  # partial unique on clawback/refund only; the ledger refuses DELETE
    ("feed_items", "media_asset_id"),              # partial unique on user_upload items only
    ("feed_items", "recall_id"),                   # partial unique on recall items only; recalls are not deleted
    ("price_alerts", "wallet_item_id"),            # partial unique on active alerts only; wallet items are soft-deleted
    ("reviews", "data_source_code"),               # reference table, never deleted
    ("wallet_items", "user_id"),                   # partial indexes on live items only; a user is soft-deleted
}

FK_GAPS = """
    SELECT r.relname, (SELECT string_agg(a.attname, ', ' ORDER BY k.ord)
                         FROM unnest(c.conkey) WITH ORDINALITY k(n, ord)
                         JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.n)
      FROM pg_constraint c JOIN pg_class r ON r.oid = c.conrelid
     WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace AND NOT r.relispartition
       AND NOT EXISTS (
           SELECT 1 FROM pg_index i
            WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1]
              AND (i.indpred IS NULL           -- or only `<first FK column> IS NOT NULL`, which an FK lookup implies
                   OR pg_get_expr(i.indpred, i.indrelid) = '(' || quote_ident(
                        (SELECT attname FROM pg_attribute WHERE attrelid = c.conrelid AND attnum = c.conkey[1]))
                      || ' IS NOT NULL)'))"""


def test_every_foreign_key_has_an_index_unless_listed(db):
    assert set(db.execute(FK_GAPS).fetchall()) == UNINDEXED_FKS


def test_the_brand_foreign_key_is_indexed(db):
    assert ("products", "brand_id") not in set(db.execute(FK_GAPS).fetchall())


def test_a_dropped_index_shows_up_as_an_unindexed_foreign_key(db):
    db.execute("DROP INDEX products_i4_idx")
    assert ("products", "brand_id") in set(db.execute(FK_GAPS).fetchall())
    with pytest.raises(psycopg.errors.UndefinedObject):
        with db.transaction():
            db.execute("DROP INDEX products_i4_idx")
