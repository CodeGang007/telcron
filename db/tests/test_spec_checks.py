"""Every CHECK in docs/database/schema_spec.py is the CHECK the migrated database enforces (DEF-060).

The backend's drift test compares columns, types, defaults and enums; CHECK constraints are not in
the mapping, so the spec-versus-database comparison for them lives here. Spec text and the database's
deparsed text differ in parentheses and casts, so each spec rule is added to an empty copy of its table
and PostgreSQL deparses both: equal deparsed text is the same rule.
"""
import importlib.util
import sys

from conftest import ROOT


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(ROOT / "docs" / "database"))
SPEC = load("schema_spec", ROOT / "docs" / "database" / "schema_spec.py")
BUILD = load("build_sql", ROOT / "docs" / "database" / "tools" / "build_sql.py")


def live_checks(db):
    """{(table, constraint): deparsed definition} for the generated `<table>_chkN` constraints."""
    rows = db.execute("""
        SELECT c.relname, k.conname, pg_get_constraintdef(k.oid)
          FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND k.contype = 'c' AND k.conname ~ '_chk[0-9]+$'
           AND k.conislocal AND NOT c.relispartition""").fetchall()
    return {(t, name): d for t, name, d in rows}


def spec_checks(db):
    """The same map for the spec: each rule deparsed by PostgreSQL on an empty copy of its table."""
    out = {}
    for t in SPEC.TABLES:
        for i, chk in enumerate(t.checks, 1):
            name = BUILD.ident(t.name, suffix=f"chk{i}")
            with db.transaction(force_rollback=True):
                db.execute(f"CREATE TEMP TABLE spec_probe (LIKE {t.name})")
                db.execute(f"ALTER TABLE spec_probe ADD CONSTRAINT probe CHECK ({chk})")
                out[(t.name, name)] = db.execute(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'probe' "
                    "AND conrelid = 'pg_temp.spec_probe'::regclass").fetchone()[0]
    return out


def test_every_check_in_the_spec_is_the_check_the_database_enforces(db):
    spec, live = spec_checks(db), live_checks(db)
    assert sorted(set(spec) - set(live)) == [], "in the spec, missing from the database"
    assert sorted(set(live) - set(spec)) == [], "in the database, missing from the spec"
    differ = {k: (spec[k], live[k]) for k in spec if spec[k] != live[k]}
    assert differ == {}, "spec (left) and database (right) disagree"


def test_a_revised_check_keeps_the_text_its_frozen_migration_was_generated_with():
    revised = [(t.name, c) for t in SPEC.TABLES for c in t.checks if isinstance(c, SPEC.Revised)]
    assert revised, "users_chk3 is revised by 20261121120000_level1_email_only"
    for table, c in revised:
        migration = (ROOT / "db" / "migrations" / c.by).read_text()
        assert c in migration, f"{table}: {c.by} does not add {c!s}"
        assert c.applied in BUILD.phase_sql(SPEC.TABLE_BY_NAME[table].phase)[0], table
