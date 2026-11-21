"""Ingestion jobs: fetch a source, keep the raw copy, turn it into registry rows, hand over.

A job is a row an admin (or the nightly schedule) creates; the Worker runs it. Every record's
raw payload is stored once, keyed by its SHA-256, so a repeat of the same content stops there
and a changed record is recognised as changed. Each record is processed in its own savepoint:
one bad record marks the job `partial`, it does not lose the rest.
"""

import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, null, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.events import audit, emit
from app.models import (
    IngestionJob,
    Recall,
    RecallProduct,
    RecallProductIdentifier,
    RecallRegion,
    SourceRecord,
)

from . import cpsc, raw_store

log = logging.getLogger("telcron.ingestion")
Fetch = Callable[[date, date], Awaitable[list[dict]]]
SOURCES: dict[str, Fetch] = {cpsc.SOURCE: cpsc.fetch}
PARSERS = {cpsc.SOURCE: cpsc.parse}
DEFAULT_DAYS = 30
MAX_DAYS = 366
# Registry products a recall may concern: an identifier in common, or a similar name and the same
# brand. The screening decides; this only chooses what is worth re-screening.
AFFECTED = text("""
    select p.id from products p
     where p.status = 'active' and (
           p.model_number_normalized = any(:ids)
        or exists (select 1 from product_aliases a
                    where a.product_id = p.id and a.alias_value = any(:ids))
        or exists (select 1 from recall_products rp join brands b on b.id = p.brand_id
                    where rp.recall_id = :recall
                      and similarity(rp.product_name, p.canonical_name) >= 0.45
                      and upper(regexp_replace(b.name, '[^A-Za-z0-9]', '', 'g')) = upper(
                          regexp_replace(coalesce(rp.brand_name, ''), '[^A-Za-z0-9]', '', 'g'))))
""")


def normalized(identifier_type: str, value: str) -> str:
    """Identifiers are compared upper-case alphanumeric; a GTIN is stored as 14 digits."""
    cleaned = "".join(ch for ch in value.upper() if ch.isalnum())
    return cleaned.zfill(14) if identifier_type == "gtin" and cleaned.isdigit() else cleaned


def window(params: dict[str, Any]) -> tuple[date, date]:
    end = date.fromisoformat(params["date_end"]) if params.get("date_end") else date.today()
    start = (date.fromisoformat(params["date_start"]) if params.get("date_start")
             else end - timedelta(days=DEFAULT_DAYS))
    if start > end or (end - start).days > MAX_DAYS:
        raise ValueError("date range must run forwards and cover at most a year")
    return start, end


async def create_job(db: AsyncSession, source: str, params: dict[str, Any], trigger: str,
                     user_id: uuid.UUID | None) -> IngestionJob:
    window(params)  # refuse a bad range before anything is queued
    job = IngestionJob(data_source_code=source, trigger=trigger, params=params,
                       triggered_by_user_id=user_id)
    db.add(job)
    await db.flush()
    emit(db, "ingestion_job", job.id, "IngestionRequested", {"job_id": str(job.id)})
    if user_id is not None:
        audit(db, action="ingestion.requested", entity_type="ingestion_job", entity_id=job.id,
              actor_user_id=user_id, actor_type="admin", changes={"source": source, **params})
    return job


def canonical(record: dict) -> bytes:
    """The bytes a record is hashed and kept as: the same content always gives the same bytes."""
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


async def keep_raw(source: str, body: bytes, digest: bytes, stats: dict[str, Any]) -> str | None:
    """Put a new record's bytes in the raw store; its key, or None when the store is off or the
    upload failed. A failure is logged and counted and costs nothing else: the record is then
    kept in the database instead, so no row is ever lost to the store."""
    if not raw_store.enabled():
        return None
    key = raw_store.key_for(source, digest, datetime.now(UTC).date())
    try:
        await raw_store.put(key, body)
    except Exception as exc:
        stats["raw_copy_failed"] = stats.get("raw_copy_failed", 0) + 1
        log.warning("raw copy not stored: source=%s sha256=%s error=%s", source, digest.hex(),
                    type(exc).__name__)
        return None
    stats["raw_copied"] = stats.get("raw_copied", 0) + 1
    return key


async def _store_recall(db: AsyncSession, source: str, record: dict, digest: bytes,
                        job_id: uuid.UUID, storage_key: str | None = None,
                        ) -> tuple[str, list[uuid.UUID]]:
    """Returns ('new' | 'changed', the registry products worth re-screening). A record kept in the
    raw store is pointed to, not repeated: the schema holds exactly one of payload and key
    (source_records_chk1)."""
    parsed = PARSERS[source](record)
    # SQL NULL, not JSON null: a JSONB column maps Python None to the JSON value.
    raw = SourceRecord(data_source_code=source, record_type="recall",
                       external_id=parsed.external_id,
                       payload=null() if storage_key else record,
                       payload_storage_key=storage_key, payload_sha256=digest,
                       ingestion_job_id=job_id)
    db.add(raw)
    await db.flush()
    recall = (await db.execute(select(Recall).where(
        Recall.data_source_code == source, Recall.external_id == parsed.external_id))
        ).scalar_one_or_none()
    outcome = "changed" if recall else "new"
    fields = {"recall_number": parsed.recall_number, "title": parsed.title,
              "description": parsed.description, "hazard": parsed.hazard,
              "remedy": parsed.remedy, "units_affected": parsed.units_affected,
              "recall_date": parsed.recall_date, "url": parsed.url,
              "source_record_id": raw.id, "synced_at": datetime.now(UTC)}
    if recall is None:
        recall = Recall(data_source_code=source, external_id=parsed.external_id, **fields)
        db.add(recall)
        await db.flush()
        db.add(RecallRegion(recall_id=recall.id, country_code="US"))
    else:
        for name, value in fields.items():
            setattr(recall, name, value)
        old = select(RecallProduct.id).where(RecallProduct.recall_id == recall.id)
        await db.execute(delete(RecallProductIdentifier).where(
            RecallProductIdentifier.recall_product_id.in_(old)))
        await db.execute(delete(RecallProduct).where(RecallProduct.recall_id == recall.id))
    await db.flush()
    identifiers: set[str] = set()
    for product in parsed.products:
        row = RecallProduct(recall_id=recall.id, product_name=product.name,
                            brand_name=product.brand, manufacturer_name=product.manufacturer,
                            image_urls=product.image_urls)
        db.add(row)
        await db.flush()
        seen: set[tuple[str, str]] = set()
        for kind, value in product.identifiers:
            key = (kind, normalized(kind, value))
            if key[1] and key not in seen:
                seen.add(key)
                identifiers.add(key[1])
                db.add(RecallProductIdentifier(recall_product_id=row.id, identifier_type=kind,
                                               value=value, value_normalized=key[1]))
    await db.flush()
    affected = (await db.execute(AFFECTED, {"ids": list(identifiers), "recall": recall.id})
                ).scalars().all()
    return outcome, list(affected)


async def run_job(job_id: uuid.UUID, fetch: Fetch | None = None) -> dict[str, Any]:
    """Run one job to the end and return its stats. Safe to run again: unchanged records stop
    at the content hash."""
    async with SessionLocal() as db:
        job = (await db.execute(select(IngestionJob).where(IngestionJob.id == job_id)
                                .with_for_update())).scalar_one()
        if job.status not in ("queued", "running"):
            return job.stats
        source = job.data_source_code
        job.status, job.started_at = "running", job.started_at or datetime.now(UTC)
        await db.commit()

        stats = {"fetched": 0, "new": 0, "changed": 0, "unchanged": 0, "errors": 0,
                 "products_rescreened": 0}
        try:
            start, end = window(job.params)
            records = await (fetch or SOURCES[source])(start, end)
        except Exception as exc:  # the source is down or refused us: the job failed, visibly
            job.status, job.error = "failed", f"{type(exc).__name__}: {exc}"[:500]
            job.stats, job.finished_at = stats, datetime.now(UTC)
            await db.commit()
            return stats

        stats["fetched"] = len(records)
        rescreen: set[uuid.UUID] = set()
        first_error = None
        for record in records:
            body = canonical(record)
            digest = hashlib.sha256(body).digest()
            external_id = str(record.get("RecallID"))
            if (await db.execute(select(SourceRecord.id).where(
                    SourceRecord.data_source_code == source,
                    SourceRecord.record_type == "recall",
                    SourceRecord.external_id == external_id,
                    SourceRecord.payload_sha256 == digest))).first():
                stats["unchanged"] += 1
                continue
            try:
                # Upload before the savepoint opens: no transaction waits on the network.
                key = await keep_raw(source, body, digest, stats)
                async with db.begin_nested():
                    outcome, affected = await _store_recall(db, source, record, digest, job.id,
                                                            key)
                stats[outcome] += 1
                rescreen.update(affected)
            except Exception as exc:
                stats["errors"] += 1
                first_error = first_error or f"record {external_id}: {type(exc).__name__}: {exc}"
        for product_id in rescreen:
            emit(db, "product", product_id, "RecallImported", {"product_id": str(product_id)})
        stats["products_rescreened"] = len(rescreen)
        job.stats, job.finished_at = stats, datetime.now(UTC)
        job.status = "partial" if stats["errors"] else "succeeded"
        job.error = first_error[:500] if first_error else None
        await db.commit()
        return stats


async def schedule_nightly(source: str = cpsc.SOURCE, days: int = 14) -> uuid.UUID:
    """The nightly sync: the last two weeks again, so late edits to a notice are picked up."""
    async with SessionLocal() as db:
        today = date.today()
        job = IngestionJob(data_source_code=source, trigger="schedule",
                           params={"date_start": (today - timedelta(days=days)).isoformat(),
                                   "date_end": today.isoformat()})
        db.add(job)
        await db.commit()
        return job.id


def job_view(job: IngestionJob) -> dict[str, Any]:
    return {"id": str(job.id), "source": job.data_source_code, "trigger": job.trigger,
            "status": job.status, "params": job.params, "stats": job.stats, "error": job.error,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None}


async def recent_recalls(db: AsyncSession, q: str, limit: int, offset: int = 0) -> list[dict[str, Any]]:
    stmt = select(Recall).where(Recall.status == "active")
    if q.strip():
        stmt = stmt.where(Recall.search_tsv.op("@@")(func.websearch_to_tsquery("english", q)))
    recalls = (await db.execute(stmt.order_by(Recall.recall_date.desc().nulls_last(),
                                              Recall.created_at.desc()).offset(offset).limit(limit))
               ).scalars().all()
    names: dict[uuid.UUID, list[str]] = {}
    images: dict[uuid.UUID, list[str]] = {}
    if recalls:
        for recall_id, name, urls in (await db.execute(
                select(RecallProduct.recall_id, RecallProduct.product_name, RecallProduct.image_urls)
                .where(RecallProduct.recall_id.in_([r.id for r in recalls])))).all():
            names.setdefault(recall_id, []).append(name)
            images.setdefault(recall_id, []).extend(u for u in urls or [] if u.startswith("https://"))
    return [{"id": str(r.id), "source": r.data_source_code, "recall_number": r.recall_number,
             "title": r.title, "hazard": r.hazard, "remedy": r.remedy,
             "recall_date": r.recall_date.isoformat() if r.recall_date else None,
             "url": r.url, "products": names.get(r.id, []),
             "image": (images.get(r.id) or [None])[0]} for r in recalls]
