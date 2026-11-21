"""Researching one product (WO-014): what the official recall databases and the web say about it.

1. CPSC recall notices whose title names the brand are imported as recalls, so the screening's
   own matching decides whether one is this product's.
2. A web search (and openFDA for food) gives pages; the model says what each says about safety.
   Each finding is stored as `web_document` evidence with its URL, tied to the product through
   `product_traceability`, and the raw result is kept as a source record.
3. The product is screened again, so its passport is rated from everything found, with citations.

A run is an ingestion job (source `web_search`): its stats are the record of what was searched,
and the cool-down and the daily cap are counted from those jobs.
"""

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.events import emit
from app.core.redis import get_redis
from app.models import (
    Brand,
    Category,
    EvidenceItem,
    IngestionJob,
    Product,
    ProductTraceability,
    Recall,
    RecallProduct,
    RecallProductIdentifier,
    RecallRegion,
    SourceRecord,
)
from app.modules.ingestion import cpsc
from app.modules.ingestion.service import _store_recall

from . import registries, web

SOURCE = "web_search"
DAILY_CAP = 15  # two Tavily searches a run; the free plan is 1,000 searches a month
PREFIX = "web_"


def _digest(*parts: str) -> bytes:
    return hashlib.sha256("\x1f".join(parts).encode()).digest()


async def _latest(db: AsyncSession, product_id: uuid.UUID) -> IngestionJob | None:
    return (await db.execute(select(IngestionJob).where(
        IngestionJob.data_source_code == SOURCE,
        IngestionJob.params["product_id"].astext == str(product_id))
        .order_by(IngestionJob.created_at.desc()).limit(1))).scalar_one_or_none()


async def request(db: AsyncSession, product: Product, user_id: uuid.UUID | None,
                  trigger: str = "event") -> IngestionJob | None:
    """Queue a research run, unless one ran recently or today's searches are spent."""
    s = get_settings()
    if not s.research_enabled:
        return None
    last = await _latest(db, product.id)
    now = datetime.now(UTC)
    if last is not None and (last.status in ("queued", "running")
                             or last.created_at > now - timedelta(hours=s.research_cooldown_hours)):
        return None
    today = await db.scalar(select(func.count()).select_from(IngestionJob).where(
        IngestionJob.data_source_code == SOURCE, IngestionJob.created_at > now - timedelta(days=1)))
    if today >= DAILY_CAP:
        return None
    job = IngestionJob(data_source_code=SOURCE, trigger=trigger,
                       params={"product_id": str(product.id)}, triggered_by_user_id=user_id)
    db.add(job)
    await db.flush()
    emit(db, "ingestion_job", job.id, "ResearchRequested", {"job_id": str(job.id)})
    return job


async def _known_urls(db: AsyncSession, product_id: uuid.UUID) -> set[str]:
    return set((await db.execute(select(EvidenceItem.url).join(
        ProductTraceability, ProductTraceability.evidence_id == EvidenceItem.id).where(
        ProductTraceability.product_id == product_id, EvidenceItem.kind == "web_document")))
        .scalars())


COUNTRY = {"gov.uk": "GB", "gc.ca": "CA", "canada.ca": "CA", "cpsc.gov": "US",
           "saferproducts.gov": "US", "fda.gov": "US", "nhtsa.gov": "US", "govt.nz": "NZ",
           "gov.au": "AU", "go.jp": "JP", "gov.in": "IN"}


async def _official_recall(db: AsyncSession, product: Product, brand: str | None,
                           finding: web.Finding, raw: SourceRecord) -> bool:
    """A government notice that this product is recalled becomes a recall in the registry, tied to
    the product by brand and name; by model number too when the notice prints it. The screening
    then judges it like any other recall: the model number makes it a match, brand and name a
    near match."""
    hit = finding.hit
    if finding.kind != "recall" or not web.official(hit) or not brand:
        return False
    source = hit.source if hit.source in web.OFFICIAL_SOURCES else "regulator_web"
    key = web.same_page(hit.url)
    tail = key.rsplit("/", 1)[-1]
    # The same notice already in the registry: imported from CPSC's feed, or found before under
    # another address of the same page.
    near = select(Recall.url).where(func.lower(Recall.url).contains(tail)) if len(tail) >= 12 \
        else select(Recall.url).where(func.lower(Recall.url).contains(key.split("/", 1)[-1]))
    if any(web.same_page(u or "") == key or (len(tail) >= 12 and (u or "").lower().rstrip("/")
           .endswith(tail)) for u in (await db.execute(near.limit(50))).scalars()):
        return False
    recall = Recall(data_source_code=source, external_id=hit.url[:500], title=hit.title[:500],
                    description=hit.snippet or None, hazard=finding.finding, url=hit.url,
                    source_record_id=raw.id, synced_at=datetime.now(UTC))
    db.add(recall)
    await db.flush()
    host = re.sub(r"^https?://", "", hit.url).split("/")[0].lower()
    country = next((c for d, c in COUNTRY.items() if host.endswith(d)), None)
    if country:
        db.add(RecallRegion(recall_id=recall.id, country_code=country))
    named = RecallProduct(recall_id=recall.id, product_name=product.canonical_name,
                          brand_name=brand)
    db.add(named)
    await db.flush()
    page = re.sub(r"[^A-Z0-9]", "", f"{hit.title} {hit.snippet}".upper())
    if product.model_number_normalized and len(product.model_number_normalized) >= 4 \
            and product.model_number_normalized in page:
        db.add(RecallProductIdentifier(recall_product_id=named.id, identifier_type="model_number",
                                       value=product.model_number,
                                       value_normalized=product.model_number_normalized))
    return True


async def _store(db: AsyncSession, product: Product, job: IngestionJob, finding: web.Finding,
                 query: str, brand: str | None = None) -> bool:
    hit = finding.hit
    payload = {"title": hit.title, "url": hit.url, "snippet": hit.snippet, "query": query,
               "kind": finding.kind, "finding": finding.finding, "product_id": str(product.id)}
    raw = SourceRecord(data_source_code=hit.source,
                       record_type="recall" if finding.kind == "recall" else "other",
                       external_id=hit.url[:500], payload=payload,
                       payload_sha256=_digest(str(product.id), hit.url, finding.finding),
                       ingestion_job_id=job.id)
    db.add(raw)
    evidence = EvidenceItem(kind="web_document", url=hit.url,
                            excerpt=f"{hit.title}: {finding.finding}"[:500])
    db.add(evidence)
    await db.flush()
    db.add(ProductTraceability(
        product_id=product.id, attribute=f"{PREFIX}{finding.kind}", value=hit.title[:300],
        evidence_id=evidence.id, match_method=f"{hit.source}+llm",
        confidence=Decimal("0.9") if finding.about_this_product else Decimal("0.6")))
    return await _official_recall(db, product, brand, finding, raw)


async def research(db: AsyncSession, job: IngestionJob) -> dict[str, Any]:
    product = (await db.execute(select(Product).where(
        Product.id == uuid.UUID(job.params["product_id"])))).scalar_one()
    brand = await db.scalar(select(Brand.name).where(Brand.id == product.brand_id))
    category = await db.scalar(select(Category.code).where(Category.id == product.category_id))
    name = product.canonical_name
    label = name if not brand or name.lower().startswith(brand.lower()) else f"{brand} {name}"
    if product.model_number and product.model_number.lower() not in label.lower():
        label = f"{label} {product.model_number}"
    stats: dict[str, Any] = {"cpsc_notices": 0, "cpsc_new": 0, "pages": 0, "findings": 0,
                             "errors": []}

    # 1. Official recalls, imported as recalls: the screening decides whether one is this product's.
    if brand:
        try:
            records = await cpsc.search(brand)
            stats["cpsc_notices"] = len(records)
            for record in records:
                digest = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"))
                                        .encode()).digest()
                if (await db.execute(select(SourceRecord.id).where(
                        SourceRecord.data_source_code == cpsc.SOURCE,
                        SourceRecord.payload_sha256 == digest))).first():
                    continue
                async with db.begin_nested():
                    _, affected = await _store_recall(db, cpsc.SOURCE, record, digest, job.id)
                stats["cpsc_new"] += 1
                for other in affected:  # products elsewhere in the registry this notice names
                    if other != product.id:
                        emit(db, "product", other, "RecallImported", {"product_id": str(other)})
        except Exception as exc:  # the source is down: say so, carry on with the rest
            stats["errors"].append(f"cpsc: {type(exc).__name__}: {exc}"[:200])

    # 2. Official registries (UK OPSS, openFDA), the open web and the regulators' own sites:
    #    pages, then what each says about safety.
    hits: list[web.Hit] = []
    query = f"{label} recall safety warning hazard"
    try:
        hits += await web.search(query)
    except web.ResearchUnavailable as exc:
        stats["errors"].append(f"web: {exc}"[:200])
    official, failed = await registries.search(f"{brand or ''} {name}".strip()[:120], category)
    hits = official + hits  # official registries first: the reader keeps the first of a URL
    stats["errors"] += failed
    known = {web.same_page(u) for u in await _known_urls(db, product.id)}
    hits = [h for h in dict((web.same_page(h.url), h) for h in hits).values()
            if web.same_page(h.url) not in known]
    stats["pages"] = len(hits)
    try:
        findings = await web.read(label, hits, brand=brand)
    except web.ResearchUnavailable as exc:
        findings = []
        stats["errors"].append(f"reader: {exc}"[:200])
    stats["official_recalls"] = 0
    for finding in findings:
        stats["official_recalls"] += await _store(db, product, job, finding, query, brand)
    stats["findings"] = len(findings)
    await db.flush()

    # 3. Rated again from everything known now.
    from app.modules.screening.service import screen_product
    await screen_product(db, product.id, "rescreen")
    return stats


async def run(job_id: uuid.UUID) -> dict[str, Any]:
    async with SessionLocal() as db:
        job = (await db.execute(select(IngestionJob).where(IngestionJob.id == job_id)
                                .with_for_update())).scalar_one()
        if job.status not in ("queued", "running"):
            return job.stats
        job.status, job.started_at = "running", datetime.now(UTC)
        await db.commit()
        try:
            stats = await research(db, job)
        except Exception as exc:
            await db.rollback()
            job = await db.get(IngestionJob, job_id)
            job.status, job.error = "failed", f"{type(exc).__name__}: {exc}"[:500]
            job.finished_at = datetime.now(UTC)
            await db.commit()
            raise
        job.stats, job.finished_at = stats, datetime.now(UTC)
        job.status = "partial" if stats["errors"] else "succeeded"
        job.error = "; ".join(stats["errors"])[:500] or None
        product_id = job.params["product_id"]
        await db.commit()
    # The new passport version replaces the cached one (as the screening handler does).
    await (await get_redis()).delete(f"telcron:passport:{product_id}")
    return stats


async def summary(db: AsyncSession, product: Product) -> dict[str, Any]:
    rows = (await db.execute(
        select(ProductTraceability.attribute, ProductTraceability.value,
               ProductTraceability.match_method, ProductTraceability.confidence,
               EvidenceItem.url, EvidenceItem.excerpt, EvidenceItem.created_at)
        .join(EvidenceItem, EvidenceItem.id == ProductTraceability.evidence_id)
        .where(ProductTraceability.product_id == product.id,
               ProductTraceability.attribute.startswith(PREFIX))
        .order_by(EvidenceItem.created_at.desc()).limit(40))).all()
    last = await _latest(db, product.id)
    s = get_settings()
    cooled = last is None or (last.status not in ("queued", "running") and last.created_at
                              <= datetime.now(UTC) - timedelta(hours=s.research_cooldown_hours))
    return {
        "enabled": s.research_enabled,
        "status": last.status if last else None,
        "searched_at": (last.finished_at or last.created_at).isoformat() if last else None,
        "stats": last.stats if last else None,
        "can_request": s.research_enabled and cooled,
        "findings": [{"kind": a.removeprefix(PREFIX), "title": v,
                      "source": m.split("+")[0], "about_this_product": float(c or 0) >= 0.9,
                      "url": u, "finding": (e or "").split(": ", 1)[-1], "found_at": t.isoformat()}
                     for a, v, m, c, u, e, t in rows],
    }
