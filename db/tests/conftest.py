"""
Test harness: builds a fresh database from the real migration files (+ schema-next phases),
then gives each test its own transaction that is rolled back afterwards.

Env:
  TELCRON_TEST_ADMIN_DSN  admin DSN of a throwaway Postgres (default: the `db-test` compose service)
"""
import os
import pathlib
import uuid

import psycopg
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
ADMIN_DSN = os.environ.get("TELCRON_TEST_ADMIN_DSN", "postgresql://postgres:test@127.0.0.1:55433/postgres")
TEST_DB = "telcron_test"

FILES = (sorted((ROOT / "db" / "migrations").glob("*.sql"))
         + [ROOT / "db" / "seeds" / "001_core_reference.sql"]
         + [ROOT / "db" / "schema-next" / f for f in
            ("phase2_schema.sql", "phase2_rules.sql", "phase3_schema.sql", "phase3_rules.sql", "seed_reference.sql")])


def up_part(sql: str) -> str:
    """dbmate files: keep only the migrate:up section."""
    if "-- migrate:down" in sql:
        sql = sql.split("-- migrate:down", 1)[0]
    return sql


def dsn_for(db):
    return ADMIN_DSN.rsplit("/", 1)[0] + "/" + db


@pytest.fixture(scope="session")
def database():
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    with psycopg.connect(dsn_for(TEST_DB), autocommit=True) as conn:
        for f in FILES:
            try:
                conn.execute(up_part(f.read_text()))
            except Exception as e:  # pragma: no cover — surfaces which file broke
                raise RuntimeError(f"applying {f.relative_to(ROOT)} failed: {e}") from e
    yield dsn_for(TEST_DB)


@pytest.fixture
def db(database):
    """A connection inside a transaction that is always rolled back."""
    with psycopg.connect(database) as conn:
        conn.autocommit = False
        yield conn
        conn.rollback()


@pytest.fixture
def committed(database):
    """Autocommit connection for tests that need real commits (concurrency); caller cleans up."""
    with psycopg.connect(database, autocommit=True) as conn:
        yield conn


# ───────────────────────── helpers ─────────────────────────
def one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row and len(row) == 1 else row


def savepoint_raises(conn, sql, params=(), match=None):
    """Assert a statement fails, keeping the outer transaction usable."""
    with pytest.raises(psycopg.Error) as ei:
        with conn.transaction():
            conn.execute(sql, params)
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    if match:
        assert match in str(ei.value), str(ei.value)
    return ei.value


def uid():
    return str(uuid.uuid4())[:8]


def make_user(conn, level=1, country="US", subdivision=None, phone=True):
    s = uid()
    return one(conn, """
        INSERT INTO users (email, email_verified_at, phone_e164, phone_verified_at, display_name,
                           referral_code, verification_level, status, country_code, subdivision_code)
        VALUES (%s, now(), %s, CASE WHEN %s THEN now() END, %s, %s, %s, 'active', %s, %s) RETURNING id""",
        (f"u{s}@example.com", f"+1555{int(s, 16) % 10**7:07d}" if phone else None, phone and level > 0,
         f"User {s}", f"REF{s}", level, country, subdivision))


def make_product(conn, name=None, brand=None, model=None, category="blenders"):
    s = uid()
    brand_id = None
    if brand:
        brand_id = one(conn, """INSERT INTO brands (name, normalized_name) VALUES (%s, lower(%s))
                                ON CONFLICT (normalized_name) DO UPDATE SET name = EXCLUDED.name RETURNING id""",
                       (brand, brand))
    return one(conn, """
        INSERT INTO products (category_id, brand_id, canonical_name, model_number, model_number_normalized,
                              identification_source, public_slug)
        VALUES ((SELECT id FROM categories WHERE code = %s), %s, %s, %s, upper(regexp_replace(%s, '[^A-Za-z0-9]', '', 'g')),
                'text', %s) RETURNING id""",
        (category, brand_id, name or f"Product {s}", model, model, f"p-{s}-{uid()}"))


def make_recall(conn, title="Blender blade detaches", source="cpsc"):
    return one(conn, """
        INSERT INTO recalls (data_source_code, external_id, title, hazard, recall_date, synced_at)
        VALUES (%s, %s, %s, 'Laceration hazard', current_date, now()) RETURNING id""", (source, uid(), title))


def make_screening(conn, product_id, verdict="no_match_found", recall_id=None, candidate_verdict=None):
    sid = one(conn, """INSERT INTO screenings (product_id, run_type, corpus_synced_at)
                       VALUES (%s, 'initial', now()) RETURNING id""", (product_id,))
    if recall_id:
        conn.execute("""INSERT INTO screening_matches (screening_id, recall_id, rank, verdict)
                        VALUES (%s, %s, 1, %s)""", (sid, recall_id, candidate_verdict or verdict))
    conn.execute("""UPDATE screenings SET status = 'completed', verdict = %s, completed_at = now() WHERE id = %s""",
                 (verdict, sid))
    return sid


def make_passport(conn, product_id, screening_id, badge="verified", tier=2, version=None):
    if version is None:
        version = one(conn, "SELECT coalesce(max(version), 0) + 1 FROM passports WHERE product_id = %s", (product_id,))
    return one(conn, """
        INSERT INTO passports (product_id, version, tier, status_badge, trust_score, screening_id, formula_version)
        VALUES (%s, %s, %s, %s, CASE WHEN %s = 2 THEN 90 END, %s, 'v1') RETURNING id""",
        (product_id, version, tier, badge, tier, screening_id))


def make_blob(conn, phash=None):
    return one(conn, """INSERT INTO media_blobs (sha256, kind, mime_type, byte_size, storage_key_original, perceptual_hash)
                        VALUES (sha256(%s::bytea), 'image', 'image/jpeg', 1000, %s, %s) RETURNING id""",
               (uid().encode(), f"orig/{uid()}.jpg", phash))


def make_asset(conn, owner, blob=None):
    blob = blob or make_blob(conn)
    return one(conn, "INSERT INTO media_assets (blob_id, owner_user_id) VALUES (%s, %s) RETURNING id", (blob, owner))
