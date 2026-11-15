"""Catalogue reads: search, one product, and the passport with the evidence behind it."""

import json
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.models import (
    Brand,
    Category,
    EvidenceItem,
    HazardAssessment,
    HazardDimension,
    HazardDimensionScore,
    HazardScoreCitation,
    Passport,
    Product,
    ProductAlias,
    ProductCertification,
    Recall,
    ScreeningMatch,
    SearchQuery,
)


def _f(value: Any) -> float | None:
    return float(value) if value is not None else None


def _summary_columns() -> list:
    return [Product.id, Product.public_slug, Product.canonical_name, Product.model_number,
            Brand.name.label("brand"), Category.name.label("category"),
            Passport.status_badge, Passport.trust_score, Passport.tier]


def _summary(row: Any) -> dict[str, Any]:
    return {"id": str(row.id), "slug": row.public_slug, "name": row.canonical_name,
            "model_number": row.model_number, "brand": row.brand, "category": row.category,
            "status_badge": row.status_badge, "trust_score": _f(row.trust_score),
            "tier": row.tier}


def _summary_query():
    return (select(*_summary_columns())
            .join(Category, Category.id == Product.category_id)
            .outerjoin(Brand, Brand.id == Product.brand_id)
            .outerjoin(Passport, Passport.id == Product.current_passport_id)
            .where(Product.status == "active"))


async def search(db: AsyncSession, q: str, limit: int, user_id: uuid.UUID | None
                 ) -> list[dict[str, Any]]:
    q = q.strip()
    db.add(SearchQuery(user_id=user_id, query_text=q[:200]))
    if not q:
        rows = (await db.execute(_summary_query().order_by(Product.created_at.desc())
                                 .limit(limit))).all()
        return [_summary(r) for r in rows]
    # An exact identifier (barcode, model number) wins outright.
    exact = (await db.execute(_summary_query().where(or_(
        Product.id.in_(select(ProductAlias.product_id).where(ProductAlias.alias_value == q)),
        Product.model_number_normalized == "".join(c for c in q.lower() if c.isalnum()),
    )).limit(limit))).all()
    if exact:
        return [_summary(r) for r in exact]
    rank = func.greatest(func.word_similarity(q, Product.canonical_name),
                         func.word_similarity(q, func.coalesce(Brand.name, "")))
    rows = (await db.execute(_summary_query().where(or_(
        Product.canonical_name.ilike(f"%{q}%"), Brand.name.ilike(f"%{q}%"), rank > 0.35))
        .order_by(rank.desc(), Product.canonical_name).limit(limit))).all()
    return [_summary(r) for r in rows]


async def find_product(db: AsyncSession, id_or_slug: str) -> Product | None:
    try:
        cond = Product.id == uuid.UUID(id_or_slug)
    except ValueError:
        cond = Product.public_slug == id_or_slug
    return (await db.execute(select(Product).where(cond, Product.status == "active"))
            ).scalar_one_or_none()


async def product_detail(db: AsyncSession, product: Product) -> dict[str, Any]:
    row = (await db.execute(_summary_query().where(Product.id == product.id))).one()
    certs = (await db.execute(select(ProductCertification).where(
        ProductCertification.product_id == product.id))).scalars().all()
    return {**_summary(row), "description": product.description,
            "specifications": product.specifications,
            "certifications": [
                {"scheme": c.scheme_code, "identifier": c.certificate_identifier,
                 "status": c.current_status,
                 "valid_until": c.valid_until.isoformat() if c.valid_until else None}
                for c in certs]}


async def passport_view(db: AsyncSession, product: Product) -> dict[str, Any] | None:
    """Cached for 24 hours; the screening handler deletes the key when it issues a new version."""
    if product.current_passport_id is None:
        return None
    redis = await get_redis()
    key = f"telcron:passport:{product.id}"
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)

    passport = await db.get(Passport, product.current_passport_id)
    assessment = (await db.get(HazardAssessment, passport.hazard_assessment_id)
                  if passport.hazard_assessment_id else None)
    dimensions: list[dict[str, Any]] = []
    if assessment is not None:
        rows = (await db.execute(
            select(HazardDimensionScore, HazardDimension)
            .join(HazardDimension, HazardDimension.code == HazardDimensionScore.dimension_code)
            .where(HazardDimensionScore.assessment_id == assessment.id)
            .order_by(HazardDimension.sort_order))).all()
        citations = (await db.execute(
            select(HazardScoreCitation.dimension_code, EvidenceItem)
            .join(EvidenceItem, EvidenceItem.id == HazardScoreCitation.evidence_id)
            .where(HazardScoreCitation.assessment_id == assessment.id))).all()
        by_dim: dict[str, list[dict[str, Any]]] = {}
        for code, ev in citations:
            by_dim.setdefault(code, []).append(
                {"id": str(ev.id), "kind": ev.kind, "excerpt": ev.excerpt, "url": ev.url})
        dimensions = [
            {"code": d.code, "name": d.name, "weight": _f(s.weight_applied), "status": s.status,
             "score": _f(s.score), "justification": s.justification,
             "citations": by_dim.get(d.code, [])}
            for s, d in rows]
    matches = []
    if passport.screening_id:
        rows = (await db.execute(
            select(ScreeningMatch, Recall).join(Recall, Recall.id == ScreeningMatch.recall_id)
            .where(ScreeningMatch.screening_id == passport.screening_id)
            .order_by(ScreeningMatch.rank))).all()
        matches = [{"recall_id": str(r.id), "title": r.title, "hazard": r.hazard,
                    "remedy": r.remedy, "url": r.url, "verdict": m.verdict,
                    "recall_date": r.recall_date.isoformat() if r.recall_date else None,
                    "confidence": _f(m.confidence), "rationale": m.rationale}
                   for m, r in rows]
    history = (await db.execute(select(Passport).where(Passport.product_id == product.id)
                                .order_by(Passport.version.desc()).limit(20))).scalars().all()
    view = {
        "product_id": str(product.id), "passport_id": str(passport.id),
        "version": passport.version, "tier": passport.tier,
        "status_badge": passport.status_badge, "trust_score": _f(passport.trust_score),
        "recall_component": _f(passport.recall_component),
        "certification_component": _f(passport.certification_component),
        "hazard_component": _f(passport.hazard_component),
        "formula_version": passport.formula_version,
        "verified_at": passport.verified_at.isoformat(),
        "hazard": None if assessment is None else {
            "total_score": _f(assessment.total_score), "label": assessment.label,
            "has_insufficient_data": assessment.has_insufficient_data,
            "model_code": assessment.model_code, "dimensions": dimensions},
        "recall_matches": matches,
        "history": [{"version": p.version, "status_badge": p.status_badge,
                     "trust_score": _f(p.trust_score), "verified_at": p.verified_at.isoformat()}
                    for p in history],
    }
    await redis.set(key, json.dumps(view), ex=get_settings().passport_cache_seconds)
    return view
