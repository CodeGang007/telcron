"""Phases 2-3 as migrations (WO-022): they must be no-ops on a database that already has them.

The local database and the AWS dev host got phases 2-3 outside dbmate (`make db-next`, the host's own
block). Their first `dbmate up` after the promotion runs these migrations against a database that
already holds everything, so running one again must succeed and change nothing.

Their down-steps refuse (S-18): where the up-step was skipped, rolling back would drop the coin ledger,
balances and redemptions that no migration created.
"""
import pathlib

import psycopg
import pytest

from conftest import ROOT, make_product, make_user, one, up_part

PROMOTED = sorted(p for p in (ROOT / "db" / "migrations").glob("20261122130*.sql"))

CATALOGUE = """
    SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public'),
           (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'),
           (SELECT count(*) FROM pg_constraint),
           (SELECT count(*) FROM pg_trigger),
           (SELECT md5(string_agg(c.relname, ',' ORDER BY c.relname)) FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public')"""

REFERENCE = """
    SELECT (SELECT count(*) FROM scoring_contexts), (SELECT count(*) FROM scoring_bands),
           (SELECT count(*) FROM hazard_dimensions), (SELECT count(*) FROM embedding_models WHERE is_active),
           (SELECT count(*) FROM coin_earn_rules), (SELECT count(*) FROM reward_levels),
           (SELECT count(*) FROM redemption_items), (SELECT count(*) FROM badges), (SELECT count(*) FROM topics)"""


def test_the_five_promoted_migrations_exist():
    assert [p.name.split("_", 1)[1] for p in PROMOTED] == [
        "phase2_schema.sql", "phase2_rules.sql", "phase3_schema.sql", "phase3_rules.sql", "phase2_3_reference.sql"]


@pytest.mark.parametrize("path", PROMOTED, ids=lambda p: p.name)
def test_a_promoted_migration_on_a_database_that_has_its_phase_changes_nothing(db, path: pathlib.Path):
    before = (one(db, CATALOGUE), one(db, REFERENCE))
    db.execute(up_part(path.read_text()))
    assert (one(db, CATALOGUE), one(db, REFERENCE)) == before


def test_a_database_with_only_part_of_a_phase_fails_loudly(db):
    # Without its sentinel table the phase looks absent, and re-creating the rest collides.
    db.execute("ALTER TABLE hazard_assessments RENAME TO hazard_assessments_moved")
    with pytest.raises(psycopg.errors.DuplicateTable):
        with db.transaction():
            db.execute(up_part(PROMOTED[0].read_text()))


def down_part(sql: str) -> str:
    """dbmate files: keep only the migrate:down section."""
    return sql.split("-- migrate:down", 1)[1]


LEDGER = "SELECT (SELECT count(*) FROM coin_ledger_entries), (SELECT count(*) FROM coin_balances)"


@pytest.mark.parametrize("path", PROMOTED, ids=lambda p: p.name)
def test_rolling_back_a_promoted_migration_is_refused_and_changes_nothing(db, path: pathlib.Path):
    user = make_user(db)
    one(db, "SELECT coin_earn(%s, 'review', %s, 'product', %s)", (user, f"s18:{user}", make_product(db)))
    before = (one(db, CATALOGUE), one(db, REFERENCE), one(db, LEDGER))
    with pytest.raises(psycopg.errors.RaiseException, match="irreversible"):
        with db.transaction():
            db.execute(down_part(path.read_text()))
    assert (one(db, CATALOGUE), one(db, REFERENCE), one(db, LEDGER)) == before
    assert one(db, LEDGER)[0] >= 1
