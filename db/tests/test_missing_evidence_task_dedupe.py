"""DEF-120: the data migration leaves at most one open missing-evidence task per product.

Tasks are inserted directly: the duplicate state is one the application can no longer produce
(DEF-032 dedupes on write), so only a pre-DEF-032 database holds it.
"""
import json

from conftest import ROOT, make_product, one, up_part

MIGRATION = ROOT / "db" / "migrations" / "20261123120000_dismiss_duplicate_missing_evidence_tasks.sql"
NOTE = "superseded: one open missing-evidence task per product (DEF-032/DEF-120)"


def task(conn, product_id, minutes_ago, task_type="hazard_insufficient_data", status="open"):
    return one(conn, """
        INSERT INTO review_tasks (task_type, subject_type, subject_id, status, payload, created_at, resolved_at)
        VALUES (%s, 'hazard_assessment', uuidv7(), %s, %s, now() - make_interval(mins => %s),
                CASE WHEN %s IN ('resolved', 'dismissed') THEN now() END)
        RETURNING id""",
        (task_type, status, json.dumps({"product_id": str(product_id)}), minutes_ago, status))


def state(conn, task_id):
    return conn.execute("SELECT status::text, resolution, resolved_at IS NOT NULL FROM review_tasks WHERE id = %s",
                        (task_id,)).fetchone()


def migrate(conn):
    conn.execute(up_part(MIGRATION.read_text()))


def test_only_the_newest_open_missing_evidence_task_of_a_product_stays_open(db):
    a, b = make_product(db), make_product(db)
    a_old, a_mid, a_new = task(db, a, 30), task(db, a, 20, status="in_progress"), task(db, a, 10)
    b_only = task(db, b, 50)
    migrate(db)

    for old in (a_old, a_mid):
        assert state(db, old) == ("dismissed", NOTE, True)
    assert state(db, a_new) == ("open", None, False)
    assert state(db, b_only) == ("open", None, False)
    assert one(db, """SELECT max(n) FROM (SELECT count(*) n FROM review_tasks
                      WHERE task_type = 'hazard_insufficient_data' AND status IN ('open', 'in_progress')
                      GROUP BY payload->>'product_id') s""") == 1


def test_other_task_types_and_closed_tasks_are_untouched(db):
    p = make_product(db)
    flags = [task(db, p, 40, task_type="hazard_flag"), task(db, p, 30, task_type="hazard_flag")]
    closed = task(db, p, 60, status="resolved")
    kept = task(db, p, 5)
    before = {t: state(db, t) for t in [*flags, closed]}
    migrate(db)

    assert {t: state(db, t) for t in [*flags, closed]} == before
    assert state(db, kept) == ("open", None, False)


def test_running_the_migration_twice_changes_nothing_more(db):
    p = make_product(db)
    task(db, p, 20)
    task(db, p, 10)
    migrate(db)
    snapshot = db.execute("SELECT id, status::text, resolved_at FROM review_tasks ORDER BY id").fetchall()
    migrate(db)
    assert db.execute("SELECT id, status::text, resolved_at FROM review_tasks ORDER BY id").fetchall() == snapshot
