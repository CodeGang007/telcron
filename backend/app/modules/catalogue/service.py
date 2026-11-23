"""Catalogue reads: search, one product, and the passport with the evidence behind it."""

import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Float, case, cast, func, null, or_, select, text, union_all
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
    Review,
    Screening,
    ScreeningMatch,
    SearchQuery,
)


def _f(value: Any) -> float | None:
    return float(value) if value is not None else None


def _summary_columns() -> list:
    return [Product.id, Product.public_slug, Product.canonical_name, Product.model_number,
            Brand.name.label("brand"), Category.name.label("category"),
            Passport.status_badge, Passport.trust_score, Passport.tier, Product.primary_media_id,
            Product.specifications["demo"].astext.label("demo")]


def _summary(row: Any) -> dict[str, Any]:
    return {"id": str(row.id), "slug": row.public_slug, "name": row.canonical_name,
            "model_number": row.model_number, "brand": row.brand, "category": row.category,
            "status_badge": row.status_badge, "trust_score": _f(row.trust_score),
            "tier": row.tier,
            "image_url": f"/api/v1/media/{row.primary_media_id}" if row.primary_media_id else None,
            "demo": row.demo == "true"}


def _summary_query():
    return (select(*_summary_columns())
            .join(Category, Category.id == Product.category_id)
            .outerjoin(Brand, Brand.id == Product.brand_id)
            .outerjoin(Passport, Passport.id == Product.current_passport_id)
            .where(Product.status == "active"))


async def search(db: AsyncSession, q: str, limit: int, user_id: uuid.UUID | None, offset: int = 0
                 ) -> list[dict[str, Any]]:
    q = q.strip()
    if user_id is not None:  # the schema logs searches per member; a visitor leaves no row
        db.add(SearchQuery(user_id=user_id, query_text=q[:200]))
    if not q:
        rows = (await db.execute(_summary_query().order_by(Product.created_at.desc())
                                 .offset(offset).limit(limit))).all()
        return [_summary(r) for r in rows]
    # An exact identifier (barcode, model number) wins outright.
    exact = (await db.execute(_summary_query().where(or_(
        Product.id.in_(select(ProductAlias.product_id).where(ProductAlias.alias_value.in_(
            {q, q.zfill(14)} if q.isdigit() and len(q) <= 14 else {q}))),
        Product.model_number_normalized == "".join(c for c in q.upper() if c.isalnum()),
    )).offset(offset).limit(limit))).all()
    if exact:
        return [_summary(r) for r in exact]
    meaning = await _by_meaning(db, q)
    if not meaning:  # no embedder, or it is down: words alone
        return [_summary(r) for r in await _by_words(db, q, offset, limit)]
    # Both lists, fused by reciprocal rank: a product found by its name and by its meaning ranks
    # first; one found only by meaning ("phone that caught fire") still appears.
    by_words = await _by_words(db, q, 0, CANDIDATES)
    score: dict[uuid.UUID, float] = {}
    for i, row in enumerate(by_words):
        score[row.id] = score.get(row.id, 0) + 1 / (RRF_K + i)
    for i, product_id in enumerate(meaning):
        score[product_id] = score.get(product_id, 0) + 1 / (RRF_K + i)
    order = sorted(score, key=lambda k: -score[k])[offset:offset + limit]
    if not order:
        return []
    rows = {r.id: r for r in (await db.execute(_summary_query().where(Product.id.in_(order)))).all()}
    return [_summary(rows[i]) for i in order if i in rows]


async def _by_words(db: AsyncSession, q: str, offset: int, limit: int) -> list[Any]:
    """Products whose name or brand is like the words, best first, read through the trigram index.

    Three short lists, each cut at offset + limit rows, are merged; nothing reads the whole table.
    - by name: a KNN walk of the GiST index `products_i1_idx`; `canonical_name <->> q` is
      1 - word_similarity(q, name), the rank the search has always used;
    - by brand: the products of the brands like the words (`brands` is small);
    - by part of a word: names containing the text (`ILIKE`, served by the same index), for
      fragments like "len" in "Blender" whose similarity is low.
    """
    window = offset + limit
    none = cast(null(), BigInteger)
    distance = Product.canonical_name.op("<->>", return_type=Float)(q)
    contains = f"%{q}%"
    near = (select(Product.id, func.row_number().over(order_by=distance).label("by_name"),
                   none.label("by_brand"), none.label("by_part"))
            .where(Product.status == "active").order_by(distance).limit(window))
    liked = (select(Brand.id, func.word_similarity(q, Brand.name).label("rank"))
             .where(or_(Brand.name.ilike(contains), func.word_similarity(q, Brand.name) > MATCH))
             .subquery("liked"))
    # Numbered after the cut, so PostgreSQL keeps only the top rows instead of sorting them all.
    top = (select(Product.id, liked.c.rank, Product.canonical_name)
           .join(liked, liked.c.id == Product.brand_id).where(Product.status == "active")
           .order_by(liked.c.rank.desc(), Product.canonical_name, Product.id).limit(window)
           .subquery("top"))
    of_brand = select(top.c.id, none, func.row_number().over(
        order_by=(top.c.rank.desc(), top.c.canonical_name, top.c.id)), none)
    part = (select(Product.id, none, none, func.row_number().over(order_by=distance))
            .where(Product.status == "active", Product.canonical_name.ilike(contains))
            .order_by(distance).limit(window))
    both = union_all(*(s.subquery().select() for s in (near, of_brand, part))).subquery()
    found = (select(both.c.id, func.min(both.c.by_name).label("by_name"),
                    func.min(both.c.by_brand).label("by_brand"),
                    func.min(both.c.by_part).label("by_part"))
             .group_by(both.c.id).subquery("found"))
    name_rank = func.word_similarity(q, Product.canonical_name)
    brand_rank = func.word_similarity(q, func.coalesce(Brand.name, ""))
    rank = func.greatest(name_rank, brand_rank)
    # Each product is placed by the list its rank came from, so a page's order does not depend on
    # how far the lists were read: page n+1 continues page n exactly.
    source = case((brand_rank > name_rank, 1), (name_rank > MATCH, 0), else_=2)
    position = case((brand_rank > name_rank, found.c.by_brand),
                    (name_rank > MATCH, found.c.by_name), else_=found.c.by_part)
    stmt = (_summary_query().join(found, found.c.id == Product.id)
            .where(or_(Product.canonical_name.ilike(contains), Brand.name.ilike(contains),
                       rank > MATCH))
            .order_by(rank.desc(), source, position.asc().nulls_last())
            .offset(offset).limit(limit))
    return list((await db.execute(stmt)).all())


MATCH = 0.35  # word similarity above which a name or brand is about the query
CANDIDATES = 50
RRF_K = 60
CLOSE = 0.38  # cosine distance under which a product is about the query (calibrated, WO-015)
NEAREST = """
    SELECT pe.product_id FROM product_embeddings pe JOIN products p ON p.id = pe.product_id
    WHERE pe.model_code = :model AND p.status = 'active'
      AND (pe.embedding::vector(DIMS)) <=> CAST(:v AS vector(DIMS)) < :close
    ORDER BY (pe.embedding::vector(DIMS)) <=> CAST(:v AS vector(DIMS)) LIMIT :n"""


async def _by_meaning(db: AsyncSession, q: str) -> list[uuid.UUID]:
    from app.modules.assistant import embedder
    from app.modules.assistant.index import vector_literal
    if not embedder.enabled() or len(q) < 3:
        return []
    try:
        [vector] = await embedder.embed([q], "query")
    except embedder.EmbedderUnavailable:
        return []
    # The only value written into the SQL is the vector's length, an integer: the HNSW index is on
    # `embedding::vector(<dims>)`, so the query must cast the same way to use it.
    sql = NEAREST.replace("DIMS", str(int(len(vector))))
    rows = await db.execute(text(sql), {"model": get_settings().embed_model,
                                        "v": vector_literal(vector), "close": CLOSE, "n": CANDIDATES})
    return list(rows.scalars())


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
    # "No match found" is true as of the recall corpus the screening read (business rule §4).
    checked_as_of = None
    if passport.screening_id:
        screening = await db.get(Screening, passport.screening_id)
        checked_as_of = screening.corpus_synced_at.isoformat()
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
        "recall_checked_as_of": checked_as_of,
        "history": [{"version": p.version, "status_badge": p.status_badge,
                     "trust_score": _f(p.trust_score), "verified_at": p.verified_at.isoformat()}
                    for p in history],
    }
    await redis.set(key, json.dumps(view), ex=get_settings().passport_cache_seconds)
    return view


SIMILAR = 0.62  # cosine similarity of two products' vectors to call them alike (bge: unrelated ~0.5)
ALTERNATIVES = """
    SELECT pe2.product_id, (pe2.embedding::vector(DIMS)) <=> (pe.embedding::vector(DIMS)) AS distance
    FROM product_embeddings pe
    JOIN product_embeddings pe2 ON pe2.model_code = pe.model_code AND pe2.product_id <> pe.product_id
    WHERE pe.product_id = :product AND pe.model_code = :model
    ORDER BY 2 LIMIT 40"""


async def alternatives(db: AsyncSession, product: Product, limit: int = 6) -> dict[str, Any]:
    """Products like this one that Telcron has verified: a current passport with the "verified"
    badge and a trust score at least as high as this product's (or 60 when it has none). Closest in
    meaning first when vectors exist, otherwise the same category by trust score."""
    mine = await db.get(Passport, product.current_passport_id) if product.current_passport_id else None
    floor = max(Decimal(60), mine.trust_score or Decimal(0)) if mine else Decimal(60)
    order: list[uuid.UUID] = []
    closeness: dict[uuid.UUID, float] = {}
    dims = await db.scalar(text("""SELECT m.dimensions FROM embedding_models m
        JOIN product_embeddings pe ON pe.model_code = m.code
        WHERE pe.product_id = :p AND m.code = :m"""), {"p": product.id, "m": get_settings().embed_model})
    if dims:
        rows = await db.execute(text(ALTERNATIVES.replace("DIMS", str(int(dims)))),
                                {"product": product.id, "model": get_settings().embed_model})
        for product_id, distance in rows:
            order.append(product_id)
            closeness[product_id] = round(1 - float(distance), 3)
    # The same kind of product only, never a fictional demo one: an alternative is something a
    # person could buy instead (a mini fridge is no alternative to a games console).
    safe = (_summary_query().where(Passport.status_badge == "verified",
                                   Passport.trust_score >= floor, Product.id != product.id,
                                   Product.category_id == product.category_id,
                                   Product.specifications["demo"].astext.is_(None)))
    if order:
        rows = {r.id: r for r in (await db.execute(safe.where(Product.id.in_(order)))).all()}
        picked = [rows[i] for i in order if i in rows and closeness[i] >= SIMILAR][:limit * 2]
    else:
        picked = []
    how = "meaning" if picked else "category"
    if not picked:  # no vectors, or nothing close: the same category, safest first
        picked = (await db.execute(safe.order_by(Passport.trust_score.desc())
                                   .limit(limit * 2))).all()
    stats = {pid: (float(avg), n) for pid, avg, n in (await db.execute(
        select(Review.product_id, func.avg(Review.rating), func.count()).where(
            Review.product_id.in_([r.id for r in picked]), Review.status == "published",
            Review.deleted_at.is_(None)).group_by(Review.product_id))).all()}
    # Safety first, then what owners say, then how alike they are.
    picked.sort(key=lambda r: (-(float(r.trust_score or 0)), -stats.get(r.id, (0, 0))[0],
                               -(closeness.get(r.id) or 0)))
    return {"basis": how, "trust_floor": float(floor),
            "items": [{**_summary(r), "closeness": closeness.get(r.id),
                       "rating": round(stats[r.id][0], 1) if r.id in stats else None,
                       "reviews": stats.get(r.id, (0, 0))[1]} for r in picked[:limit]]}
