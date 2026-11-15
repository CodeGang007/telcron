"""One screening: retrieve evidence, score, check every citation, issue a passport version.

Vector retrieval (Titan + pgvector) is not wired — WO-004. Recall candidates come from
identifier equality and trigram similarity only.
"""

import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import audit, emit
from app.domain import passport as passport_rules
from app.domain.hazard import DimensionScore, label_for, total_score
from app.models import (
    AiInvocation,
    Brand,
    CertificationCheck,
    EvidenceItem,
    HazardAssessment,
    HazardDimension,
    HazardDimensionScore,
    HazardFlag,
    HazardScoreCitation,
    Passport,
    PassportEvidence,
    Product,
    ProductAlias,
    ProductCertification,
    Recall,
    RecallProduct,
    RecallProductIdentifier,
    Review,
    ReviewTask,
    RiskEvent,
    Screening,
    ScreeningMatch,
)

from .scorer import DimensionSpec, EvidenceRef, Scorer, get_scorer

CONTEXT = "consumer_product"
SIMILARITY_FLOOR = 0.45
MAX_REVIEWS = 40


def _norm(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


async def _evidence_for(db: AsyncSession, column, value: uuid.UUID, kind: str,
                        excerpt: str | None, url: str | None = None) -> EvidenceItem:
    """evidence_items is append-only: one row per underlying fact, reused by later screenings."""
    row = (await db.execute(select(EvidenceItem).where(column == value).limit(1))
           ).scalar_one_or_none()
    if row is None:
        row = EvidenceItem(kind=kind, excerpt=(excerpt or "")[:500] or None, url=url,
                           **{column.key: value})
        db.add(row)
        await db.flush()
    return row


async def _recall_candidates(db: AsyncSession, product: Product, brand: str | None
                             ) -> list[tuple[Recall, str, Decimal, float, str]]:
    identifiers = {_norm(v) for v in (await db.execute(select(ProductAlias.alias_value).where(
        ProductAlias.product_id == product.id))).scalars()}
    if product.model_number_normalized:
        identifiers.add(product.model_number_normalized)
    found: dict[uuid.UUID, tuple[Recall, str, Decimal, float, str]] = {}
    if identifiers:
        rows = (await db.execute(
            select(Recall, RecallProductIdentifier.value)
            .join(RecallProduct, RecallProduct.recall_id == Recall.id)
            .join(RecallProductIdentifier,
                  RecallProductIdentifier.recall_product_id == RecallProduct.id)
            .where(RecallProductIdentifier.value_normalized.in_(identifiers)))).all()
        for recall, value in rows:
            found[recall.id] = (recall, "match", Decimal("0.950"), 1.0,
                                f"Recall identifier {value} equals a product identifier.")
    sim = func.similarity(RecallProduct.product_name, product.canonical_name)
    rows = (await db.execute(
        select(Recall, sim, RecallProduct.brand_name)
        .join(RecallProduct, RecallProduct.recall_id == Recall.id)
        .where(sim >= SIMILARITY_FLOOR).order_by(sim.desc()).limit(10))).all()
    for recall, score, recall_brand in rows:
        if recall.id in found:
            continue
        same_brand = bool(brand and recall_brand and _norm(brand) == _norm(recall_brand))
        if same_brand:
            found[recall.id] = (recall, "possible", Decimal(str(round(float(score), 3))),
                                float(score), "Similar product name and the same brand.")
    return list(found.values())


async def screen_product(db: AsyncSession, product_id: uuid.UUID, run_type: str,
                         scorer: Scorer | None = None) -> Passport:
    scorer = scorer or get_scorer()
    product = (await db.execute(select(Product).where(Product.id == product_id).with_for_update())
               ).scalar_one()
    brand = await db.scalar(select(Brand.name).where(Brand.id == product.brand_id))
    screening = Screening(product_id=product.id, run_type=run_type, status="running",
                          model_code=scorer.model_code, prompt_version=scorer.prompt_version)
    db.add(screening)
    await db.flush()

    # 1. Evidence.
    refs: list[EvidenceRef] = []
    purpose: dict[str, str] = {}
    candidates = await _recall_candidates(db, product, brand)
    for recall, *_ in candidates:
        ev = await _evidence_for(db, EvidenceItem.recall_id, recall.id, "recall",
                                 f"{recall.title}. {recall.hazard or ''}", recall.url)
        refs.append(EvidenceRef(str(ev.id), "recall",
                                f"recall {recall.title} {recall.hazard or ''}"))
        purpose[str(ev.id)] = "recall"
    certs = (await db.execute(select(ProductCertification).where(
        ProductCertification.product_id == product.id))).scalars().all()
    for cert in certs:
        if cert.last_check_id is None:
            continue
        check = await db.get(CertificationCheck, cert.last_check_id)
        ev = await _evidence_for(db, EvidenceItem.certification_check_id, check.id,
                                 "certification",
                                 f"{cert.scheme_code} {cert.certificate_identifier}: "
                                 f"{check.status}")
        refs.append(EvidenceRef(str(ev.id), "certification", ev.excerpt or ""))
        purpose[str(ev.id)] = "certification"
    reviews = (await db.execute(select(Review).where(
        Review.product_id == product.id, Review.status == "published", Review.deleted_at.is_(None))
        .order_by(Review.created_at.desc()).limit(MAX_REVIEWS))).scalars().all()
    for review in reviews:
        ev = await _evidence_for(db, EvidenceItem.review_id, review.id, "review",
                                 f"{review.rating}/5 {review.title or ''} {review.body}")
        refs.append(EvidenceRef(str(ev.id), "review", ev.excerpt or ""))
        purpose[str(ev.id)] = "hazard"
    flags = (await db.execute(select(HazardFlag).where(
        HazardFlag.product_id == product.id, HazardFlag.status == "confirmed"))).scalars().all()
    for flag in flags:
        ev = await _evidence_for(db, EvidenceItem.hazard_flag_id, flag.id, "hazard_flag",
                                 flag.description)
        refs.append(EvidenceRef(str(ev.id), "hazard_flag", ev.excerpt or ""))
        purpose[str(ev.id)] = "hazard"

    # 2. Recall verdict.
    verdicts = {v for _, v, *_ in candidates}
    verdict = ("confirmed_match" if "match" in verdicts
               else "possible_match" if "possible" in verdicts else "no_match")
    ranked = sorted(candidates, key=lambda c: -c[3])
    for rank, (recall, v, confidence, retrieval, why) in enumerate(ranked, 1):
        db.add(ScreeningMatch(screening_id=screening.id, recall_id=recall.id, rank=rank,
                              retrieval_score=retrieval, verdict=v, confidence=confidence,
                              rationale=why))

    # 3. Score.
    dims = (await db.execute(select(HazardDimension).where(
        HazardDimension.context_code == CONTEXT, HazardDimension.is_active)
        .order_by(HazardDimension.sort_order))).scalars().all()
    started = time.monotonic()
    results = await scorer.score(
        f"{brand or ''} {product.canonical_name}. {product.description or ''}",
        [DimensionSpec(d.code, d.name, d.description) for d in dims], refs)
    db.add(AiInvocation(purpose="hazard_score", model_code=scorer.model_code,
                        prompt_version=scorer.prompt_version, subject_type="product",
                        subject_id=product.id, succeeded=True,
                        latency_ms=int((time.monotonic() - started) * 1000)))

    # 4. Check every citation. A score that cites nothing real is not a score.
    offered = {r.id for r in refs}
    by_code = {r.code: r for r in results}
    assessment = HazardAssessment(product_id=product.id, context_code=CONTEXT,
                                  input_modalities=["text"], model_code=scorer.model_code,
                                  prompt_version=scorer.prompt_version)
    db.add(assessment)
    await db.flush()
    scored: list[DimensionScore] = []
    cited: set[str] = set()
    for dim in dims:
        result = by_code.get(dim.code)
        valid = [cid for cid in (result.citations if result else []) if cid in offered]
        score = result.score if (result and valid) else None
        if score is not None:
            score = max(Decimal(0), min(Decimal(100), score))
        scored.append(DimensionScore(dim.code, dim.weight, score))
        db.add(HazardDimensionScore(
            assessment_id=assessment.id, dimension_code=dim.code, context_code=CONTEXT,
            status="scored" if score is not None else "insufficient", score=score,
            weight_applied=dim.weight, justification=result.justification if result else None))
        for cid in dict.fromkeys(valid):
            db.add(HazardScoreCitation(assessment_id=assessment.id, dimension_code=dim.code,
                                       evidence_id=uuid.UUID(cid)))
            cited.add(cid)
    total = total_score(scored)
    label = label_for(total)
    assessment.total_score, assessment.label = total, label
    assessment.has_insufficient_data = any(s.score is None for s in scored)

    # 5. Passport: a new version, never an edit.
    previous = (await db.get(Passport, product.current_passport_id)
                if product.current_passport_id else None)
    built = passport_rules.build(verdict, [c.current_status for c in certs], total, label)
    passport = Passport(
        product_id=product.id, version=(previous.version + 1) if previous else 1,
        tier=built.tier, status_badge=built.status_badge, trust_score=built.trust_score,
        recall_component=built.recall_component,
        certification_component=built.certification_component,
        hazard_component=built.hazard_component, screening_id=screening.id,
        hazard_assessment_id=assessment.id, formula_version=passport_rules.FORMULA_VERSION)
    db.add(passport)
    await db.flush()
    for cid in cited | {r.id for r in refs if purpose[r.id] != "hazard"}:
        db.add(PassportEvidence(passport_id=passport.id, evidence_id=uuid.UUID(cid),
                                purpose=purpose[cid]))
    product.current_passport_id = passport.id
    screening.status, screening.verdict = "succeeded", verdict
    screening.candidates_considered = len(candidates)
    screening.completed_at = datetime.now(UTC)
    screening.rationale = f"{len(refs)} evidence items; hazard {label or 'insufficient'}."

    # 6. People and alerts.
    if label in ("medium", "high") or assessment.has_insufficient_data:
        db.add(ReviewTask(task_type="screening", subject_type="passport", subject_id=passport.id,
                          priority={"high": 2, "medium": 1}.get(label or "", 0),
                          payload={"product_id": str(product.id), "label": label,
                                   "insufficient": assessment.has_insufficient_data}))
    changed = previous is not None and (previous.status_badge != passport.status_badge
                                        or previous.tier != passport.tier)
    alarming = passport.status_badge in ("recalled", "blocked")
    if changed or (previous is None and alarming):
        event = RiskEvent(
            product_id=product.id,
            event_type="recall" if passport.status_badge == "recalled" else "hazard_change",
            severity="critical" if passport.status_badge == "recalled"
            else "high" if label == "high" else "medium" if label == "medium" else "low",
            screening_id=screening.id, hazard_assessment_id=assessment.id,
            title=f"{product.canonical_name}: passport is now {passport.status_badge}",
            summary=screening.rationale)
        db.add(event)
        await db.flush()
        emit(db, "passport", passport.id, "PassportIssued",
             {"product_id": str(product.id), "passport_id": str(passport.id),
              "risk_event_id": str(event.id)})
    audit(db, action="passport.issue", entity_type="passport", entity_id=passport.id,
          changes={"version": passport.version, "badge": passport.status_badge})
    return passport


async def open_review_tasks(db: AsyncSession, limit: int = 50) -> list[ReviewTask]:
    return list((await db.execute(
        select(ReviewTask).where(or_(ReviewTask.status == "open",
                                     ReviewTask.status == "in_progress"))
        .order_by(ReviewTask.priority.desc(), ReviewTask.created_at).limit(limit))).scalars())
