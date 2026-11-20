"""One screening: gather evidence, judge recall candidates, score the hazard dimensions, check
every citation, issue a passport version.

The database enforces the invariants (db/migrations/*_rules.sql, db/schema-next/*_rules.sql):
a screening completes exactly once; a match verdict cites a matching candidate; a scored
dimension cites evidence; assessments and passports are insert-only; a passport's version is the
next one and its badge agrees with its screening. This module orders its writes to satisfy those
rules and never works around them.

Vector retrieval (Titan + pgvector) is not wired — WO-004. Recall candidates come from
identifier equality and name similarity only.
"""

import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import audit, emit
from app.domain import passport as passport_rules
from app.domain.hazard import DimensionScore, total_score
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

CONTEXT = "safety"
SIMILARITY_FLOOR = 0.45
MAX_REVIEWS = 40
SETTING = text("select coalesce((select (value #>> '{}')::numeric from app_settings "
               "where key = :key), cast(:fallback as numeric))")
BAND = text("select label from scoring_bands where context_code = :context "
            "and score_range @> cast(:total as numeric)")
ALERT_THRESHOLD = text("select alert_threshold from scoring_contexts where code = :context")


def _norm(value: str) -> str:
    """Identifiers are compared upper-case and alphanumeric only, as the schema normalises them."""
    return "".join(ch for ch in value.upper() if ch.isalnum())


async def _evidence_for(db: AsyncSession, column, value: uuid.UUID, kind: str,
                        excerpt: str | None, url: str | None = None) -> EvidenceItem:
    """evidence_items is insert-only: one row per underlying fact, reused by later screenings."""
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
        if brand and recall_brand and _norm(brand) == _norm(recall_brand):
            found[recall.id] = (recall, "near_match", Decimal(str(round(float(score), 3))),
                                float(score), "Similar product name and the same brand.")
    return list(found.values())


async def _issue(db: AsyncSession, product: Product, screening: Screening,
                 assessment: HazardAssessment | None, built: passport_rules.PassportResult,
                 evidence: dict[str, str]) -> Passport:
    """Insert the next passport version. A trigger checks it and repoints the product."""
    version = await db.scalar(select(func.coalesce(func.max(Passport.version), 0) + 1).where(
        Passport.product_id == product.id))
    passport = Passport(
        product_id=product.id, version=version, tier=built.tier,
        status_badge=built.status_badge, trust_score=built.trust_score,
        recall_component=built.recall_component,
        certification_component=built.certification_component,
        hazard_component=built.hazard_component, screening_id=screening.id,
        hazard_assessment_id=assessment.id if assessment else None,
        formula_version=passport_rules.FORMULA_VERSION)
    db.add(passport)
    await db.flush()
    for evidence_id, purpose in evidence.items():
        db.add(PassportEvidence(passport_id=passport.id, evidence_id=uuid.UUID(evidence_id),
                                purpose=purpose))
    await db.flush()
    await db.refresh(product)
    audit(db, action="passport.issued", entity_type="passport", entity_id=passport.id,
          changes={"version": passport.version, "badge": passport.status_badge})
    return passport


async def screen_product(db: AsyncSession, product_id: uuid.UUID, run_type: str,
                         scorer: Scorer | None = None) -> Passport:
    scorer = scorer or get_scorer()
    product = (await db.execute(select(Product).where(Product.id == product_id).with_for_update())
               ).scalar_one()
    brand = await db.scalar(select(Brand.name).where(Brand.id == product.brand_id))
    previous = (await db.get(Passport, product.current_passport_id)
                if product.current_passport_id else None)
    previous_verdict = previous_total = None
    if previous is not None and previous.screening_id:
        previous_verdict = await db.scalar(
            select(Screening.verdict).where(Screening.id == previous.screening_id))
    if previous is not None and previous.hazard_assessment_id:
        previous_total = await db.scalar(select(HazardAssessment.total_score).where(
            HazardAssessment.id == previous.hazard_assessment_id))

    now = datetime.now(UTC)
    screening = Screening(product_id=product.id, run_type=run_type, corpus_synced_at=now,
                          model_code=scorer.model_code, prompt_version=scorer.prompt_version)
    db.add(screening)
    await db.flush()

    # 0. An unidentified product is not screened: nothing can be claimed about it.
    floor = await db.scalar(SETTING, {"key": "identify.confidence_threshold", "fallback": "0.75"})
    if product.identity_confidence is not None and product.identity_confidence < floor:
        screening.status, screening.verdict = "completed", "insufficient_information"
        screening.candidates_considered, screening.completed_at = 0, now
        screening.rationale = "Identity confidence is below the threshold; not screened."
        await db.flush()
        return await _issue(db, product, screening, None, passport_rules.unidentified(), {})

    # 1. Evidence. `purpose` records why each item may be cited on the passport.
    refs: list[EvidenceRef] = []
    purpose: dict[str, str] = {}
    candidates = await _recall_candidates(db, product, brand)
    for recall, *_ in candidates:
        ev = await _evidence_for(db, EvidenceItem.recall_id, recall.id, "recall",
                                 f"{recall.title}. {recall.hazard or ''}", recall.url)
        refs.append(EvidenceRef(str(ev.id), "recall",
                                f"recall {recall.title} {recall.hazard or ''}"))
        purpose[str(ev.id)] = "recall"
    # A trigger keeps each certificate's status and last check current, so read them fresh
    # rather than from whatever this session loaded earlier.
    certs = (await db.execute(select(ProductCertification).where(
        ProductCertification.product_id == product.id)
        .execution_options(populate_existing=True))).scalars().all()
    bad_check_id = None
    for cert in certs:
        if cert.last_check_id is None:
            continue
        check = await db.get(CertificationCheck, cert.last_check_id)
        ev = await _evidence_for(db, EvidenceItem.certification_check_id, check.id,
                                 "certification_check",
                                 f"{cert.scheme_code} {cert.certificate_identifier}: "
                                 f"{check.status}")
        refs.append(EvidenceRef(str(ev.id), "certification_check", ev.excerpt or ""))
        purpose[str(ev.id)] = "certification"
        if check.status in passport_rules.BAD_CERTIFICATE:
            bad_check_id = check.id
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

    # 2. Recall verdict. The candidates go in first: the verdict must be able to cite one.
    verdicts = {v for _, v, *_ in candidates}
    verdict = ("match" if "match" in verdicts
               else "near_match" if "near_match" in verdicts else "no_match_found")
    ranked = sorted(candidates, key=lambda c: -c[3])
    for rank, (recall, v, confidence, retrieval, why) in enumerate(ranked, 1):
        db.add(ScreeningMatch(screening_id=screening.id, recall_id=recall.id, rank=rank,
                              retrieval_score=retrieval, verdict=v, confidence=confidence,
                              rationale=why))
    await db.flush()
    screening.status, screening.verdict = "completed", verdict
    screening.candidates_considered = len(candidates)
    screening.completed_at = datetime.now(UTC)
    await db.flush()

    # 3. Score, then check every citation. A score that cites nothing real is not a score.
    dims = (await db.execute(select(HazardDimension).where(
        HazardDimension.context_code == CONTEXT, HazardDimension.is_active)
        .order_by(HazardDimension.sort_order))).scalars().all()
    started = time.monotonic()
    results = await scorer.score(
        f"{brand or ''} {product.canonical_name}. {product.description or ''}",
        [DimensionSpec(d.code, d.name, d.description) for d in dims], refs)
    usage = getattr(scorer, "usage", {}) or {}
    error = getattr(scorer, "error", None)
    db.add(AiInvocation(purpose="hazard_score", model_code=scorer.model_code,
                        prompt_version=scorer.prompt_version, subject_type="product",
                        subject_id=product.id, succeeded=error is None, error=error,
                        input_tokens=usage.get("input"), output_tokens=usage.get("output"),
                        latency_ms=int((time.monotonic() - started) * 1000)))
    offered = {r.id for r in refs}
    by_code = {r.code: r for r in results}
    scored: list[DimensionScore] = []
    rows: list[tuple[HazardDimension, Decimal | None, list[str], str | None]] = []
    for dim in dims:
        result = by_code.get(dim.code)
        valid = list(dict.fromkeys(
            cid for cid in (result.citations if result else []) if cid in offered))
        score = result.score if (result and valid) else None
        if score is not None:
            score = max(Decimal(0), min(Decimal(100), score))
        scored.append(DimensionScore(dim.code, dim.weight, score))
        rows.append((dim, score, valid, result.justification if result else None))
    total = total_score(scored)
    label = (await db.scalar(BAND, {"context": CONTEXT, "total": total})
             if total is not None else None)

    # 4. The assessment is insert-only, so it is written once, complete; scores before citations.
    assessment = HazardAssessment(
        product_id=product.id, context_code=CONTEXT, total_score=total, label=label,
        input_modalities=["text"], has_insufficient_data=any(s.score is None for s in scored),
        model_code=scorer.model_code, prompt_version=scorer.prompt_version)
    db.add(assessment)
    await db.flush()
    for dim, score, _, justification in rows:
        db.add(HazardDimensionScore(
            assessment_id=assessment.id, dimension_code=dim.code, context_code=CONTEXT,
            status="scored" if score is not None else "insufficient_data", score=score,
            weight_applied=dim.weight, justification=justification))
    await db.flush()
    cited: set[str] = set()
    for dim, score, valid, _ in rows:
        if score is None:
            continue
        for cid in valid:
            db.add(HazardScoreCitation(assessment_id=assessment.id, dimension_code=dim.code,
                                       evidence_id=uuid.UUID(cid)))
            cited.add(cid)
    await db.flush()

    # 5. Passport: a new version, never an edit.
    built = passport_rules.build(verdict, [c.current_status for c in certs], total)
    on_passport = {cid: purpose[cid] for cid in purpose
                   if cid in cited or purpose[cid] != "hazard"}
    passport = await _issue(db, product, screening, assessment, built, on_passport)

    # 6. People. The schema has no review-task type for a Medium or High band, only for
    #    missing evidence, so a band alone opens no task (recorded in WO-011).
    if assessment.has_insufficient_data:
        db.add(ReviewTask(task_type="hazard_insufficient_data", subject_type="hazard_assessment",
                          subject_id=assessment.id, priority=3,
                          payload={"product_id": str(product.id),
                                   "passport_id": str(passport.id)}))

    # 7. Risk events, only when something became true that was not true before.
    events: list[tuple[str, str, str, dict]] = []
    top_recall = ranked[0][0].id if ranked else None
    if verdict == "match" and previous_verdict != "match":
        events.append(("recall_match", "critical", "has been recalled", {"recall_id": top_recall}))
    elif verdict == "near_match" and previous_verdict not in ("match", "near_match"):
        events.append(("recall_near_match", "high", "may be affected by a recall",
                       {"recall_id": top_recall}))
    if built.status_badge == "certification_issue" and bad_check_id is not None and (
            previous is None or previous.status_badge != "certification_issue"):
        events.append(("certification_change", "medium", "has a certificate problem",
                       {"certification_check_id": bad_check_id}))
    threshold = await db.scalar(ALERT_THRESHOLD, {"context": CONTEXT})
    if (total is not None and threshold is not None and total >= threshold
            and (previous_total is None or previous_total < threshold)):
        events.append(("hazard_threshold", "high", "crossed the hazard alert threshold",
                       {"hazard_assessment_id": assessment.id}))
    for event_type, severity, what, links in events:
        event = RiskEvent(product_id=product.id, event_type=event_type, severity=severity,
                          screening_id=screening.id,
                          title=f"{product.canonical_name} {what}"[:200], **links)
        db.add(event)
        await db.flush()
        emit(db, "risk_event", event.id, "RiskEventRaised",
             {"product_id": str(product.id), "passport_id": str(passport.id),
              "risk_event_id": str(event.id)})
    return passport


async def open_review_tasks(db: AsyncSession, limit: int = 50) -> list[ReviewTask]:
    return list((await db.execute(
        select(ReviewTask).where(or_(ReviewTask.status == "open",
                                     ReviewTask.status == "in_progress"))
        .order_by(ReviewTask.priority, ReviewTask.created_at).limit(limit))).scalars())
