"""DEF-113 (CT-003 §A): a screening records the date of the recall corpus it checked against, not
its own clock. "No recall found" is true as of the last time CPSC's recalls were refreshed: the
newest CPSC import that did not fail, or a research run whose stats say CPSC answered.

Each test works inside one transaction it rolls back, so the jobs it writes (one of them finishes
in the future) never reach another test.
"""

from datetime import UTC, datetime, timedelta

from helpers import product_id
from sqlalchemy import select, update

from app.models import IngestionJob, Screening
from app.modules.screening.service import screen_product

SLUG = "voltpro-65w-charger"


def _job(source: str, status: str, finished: datetime, stats: dict | None = None) -> IngestionJob:
    return IngestionJob(data_source_code=source, trigger="schedule", status=status,
                        stats=stats or {}, started_at=finished - timedelta(seconds=5),
                        finished_at=finished)


async def _screened_corpus_date(db, pid) -> datetime:
    passport = await screen_product(db, pid, "rescreen")
    return await db.scalar(select(Screening.corpus_synced_at).where(
        Screening.id == passport.screening_id))


async def _forget_earlier_imports(db) -> None:
    """Jobs other tests left (a research run whose CPSC answered counts) stop counting, inside
    this transaction only."""
    await db.execute(update(IngestionJob).where(
        IngestionJob.data_source_code.in_(("cpsc", "web_search"))).values(status="failed"))


async def test_a_screening_records_the_newest_successful_cpsc_import(db):
    pid = await product_id(db, SLUG)
    await _forget_earlier_imports(db)
    now = datetime.now(UTC)
    imported = _job("cpsc", "partial", now - timedelta(seconds=40))
    db.add_all([
        imported,
        # Newer, but none of these refreshed the corpus at or before the screening.
        _job("cpsc", "failed", now - timedelta(seconds=30)),
        _job("web_search", "partial", now - timedelta(seconds=20),
             {"sources": {"cpsc": "failed", "web": "not_configured"}}),
        _job("web_search", "succeeded", now - timedelta(seconds=10)),  # before CT-003: no sources
        _job("cpsc", "succeeded", now + timedelta(hours=1)),
    ])
    await db.flush()
    try:
        assert await _screened_corpus_date(db, pid) == imported.finished_at

        # A research run whose brand search CPSC answered refreshed the corpus too.
        researched = _job("web_search", "partial", now - timedelta(seconds=5),
                          {"sources": {"cpsc": "answered", "web": "not_configured"}})
        db.add(researched)
        await db.flush()
        assert await _screened_corpus_date(db, pid) == researched.finished_at
    finally:
        await db.rollback()


async def test_with_no_recall_import_the_screening_falls_back_to_its_own_time(db):
    pid = await product_id(db, SLUG)
    await _forget_earlier_imports(db)
    try:
        before = datetime.now(UTC)
        corpus = await _screened_corpus_date(db, pid)
        assert before <= corpus <= datetime.now(UTC)
    finally:
        await db.rollback()
