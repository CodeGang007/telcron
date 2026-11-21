"""Keeps the vectors current (WO-015). A product's vector describes what it is and what is known
about its safety; every evidence item a product can cite gets one; recalls get one each, so recall
candidates can be found by meaning as well as by name. Re-embedded only when the text changes."""

import hashlib
import uuid

from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Brand,
    Category,
    EvidenceEmbedding,
    EvidenceItem,
    HazardFlag,
    Passport,
    PassportEvidence,
    Product,
    ProductEmbedding,
    ProductTraceability,
    RecallEmbedding,
    Review,
)

from . import embedder

MAX_EVIDENCE = 200


async def product_text(db: AsyncSession, product: Product) -> str:
    brand = await db.scalar(select(Brand.name).where(Brand.id == product.brand_id))
    category = await db.scalar(select(Category.name).where(Category.id == product.category_id))
    found = (await db.execute(select(ProductTraceability.attribute, ProductTraceability.value).where(
        ProductTraceability.product_id == product.id,
        ProductTraceability.attribute.startswith("web_")).limit(8))).all()
    parts = [product.canonical_name, f"Brand: {brand}" if brand else "",
             f"Model: {product.model_number}" if product.model_number else "",
             f"Category: {category}" if category else "", product.description or "",
             " ".join(f"{a.removeprefix('web_')}: {v}." for a, v in found)]
    return " ".join(p for p in parts if p)[:2000]


async def evidence_for(db: AsyncSession, product_id: uuid.UUID) -> list[uuid.UUID]:
    """Every evidence item this product can be asked about: what research found, what its
    passports cite (recalls, certificates), its reviews and confirmed hazard reports."""
    web = select(ProductTraceability.evidence_id).where(ProductTraceability.product_id == product_id)
    cited = select(PassportEvidence.evidence_id).join(
        Passport, Passport.id == PassportEvidence.passport_id).where(Passport.product_id == product_id)
    own = select(EvidenceItem.id).where(or_(
        EvidenceItem.review_id.in_(select(Review.id).where(Review.product_id == product_id)),
        EvidenceItem.hazard_flag_id.in_(select(HazardFlag.id).where(HazardFlag.product_id == product_id))))
    rows = await db.execute(select(EvidenceItem.id).where(or_(
        EvidenceItem.id.in_(web), EvidenceItem.id.in_(cited), EvidenceItem.id.in_(own)))
        .order_by(EvidenceItem.created_at.desc()).limit(MAX_EVIDENCE))
    return list(rows.scalars())


async def index_product(db: AsyncSession, product_id: uuid.UUID) -> dict[str, int]:
    """The product's vector and its evidence's vectors. Raises EmbedderUnavailable if the embedder
    is down: the caller retries later."""
    model = get_settings().embed_model
    product = await db.get(Product, product_id)
    if product is None:
        return {"product": 0, "evidence": 0}
    body = await product_text(db, product)
    digest = hashlib.sha256(body.encode()).digest()
    current = await db.scalar(select(ProductEmbedding.content_sha256).where(
        ProductEmbedding.product_id == product_id, ProductEmbedding.model_code == model))
    done = {"product": 0, "evidence": 0}
    if current != digest:
        [vector] = await embedder.embed([body])
        await db.execute(insert(ProductEmbedding).values(
            product_id=product_id, model_code=model, content_sha256=digest, embedding=vector)
            .on_conflict_do_update(index_elements=["product_id", "model_code"],
                                   set_={"content_sha256": digest, "embedding": vector}))
        done["product"] = 1
    ids = await evidence_for(db, product_id)
    have = set((await db.execute(select(EvidenceEmbedding.evidence_id).where(
        EvidenceEmbedding.evidence_id.in_(ids), EvidenceEmbedding.model_code == model))).scalars())
    todo = (await db.execute(select(EvidenceItem.id, EvidenceItem.kind, EvidenceItem.excerpt).where(
        EvidenceItem.id.in_([i for i in ids if i not in have])))).all()
    todo = [(i, f"{kind.replace('_', ' ')}: {excerpt}") for i, kind, excerpt in todo if excerpt]
    if todo:
        vectors = await embedder.embed([t for _, t in todo])
        for (evidence_id, _), vector in zip(todo, vectors, strict=True):
            db.add(EvidenceEmbedding(evidence_id=evidence_id, model_code=model, embedding=vector))
        done["evidence"] = len(todo)
    await db.flush()
    return done


async def backfill(db: AsyncSession, limit: int = 100) -> dict[str, int]:
    """Products with no vector for the active model, and recalls: the nightly catch-up."""
    model = get_settings().embed_model
    missing = (await db.execute(select(Product.id).where(
        Product.status == "active", ~Product.id.in_(select(ProductEmbedding.product_id).where(
            ProductEmbedding.model_code == model))).limit(limit))).scalars().all()
    for product_id in missing:
        await index_product(db, product_id)
    return {"products": len(missing), "recalls": await index_recalls(db, limit * 2)}


async def index_recalls(db: AsyncSession, limit: int = 200) -> int:
    """Recalls without a vector for the active model (or whose text changed)."""
    model = get_settings().embed_model
    rows = (await db.execute(text("""
        SELECT r.id, r.title, coalesce(r.hazard, ''), coalesce(string_agg(rp.product_name || ' '
               || coalesce(rp.brand_name, ''), '; '), '')
        FROM recalls r LEFT JOIN recall_products rp ON rp.recall_id = r.id
        LEFT JOIN recall_embeddings e ON e.recall_id = r.id AND e.model_code = :model
        WHERE e.recall_id IS NULL
        GROUP BY r.id ORDER BY r.recall_date DESC NULLS LAST LIMIT :limit"""),
        {"model": model, "limit": limit})).all()
    if not rows:
        return 0
    bodies = [f"{title}. Products: {names}. Hazard: {hazard}"[:2000] for _, title, hazard, names in rows]
    vectors = await embedder.embed(bodies)
    for (recall_id, *_), body, vector in zip(rows, bodies, vectors, strict=True):
        await db.execute(insert(RecallEmbedding).values(
            recall_id=recall_id, model_code=model,
            content_sha256=hashlib.sha256(body.encode()).digest(), embedding=vector)
            .on_conflict_do_nothing())
    await db.flush()
    return len(rows)


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
