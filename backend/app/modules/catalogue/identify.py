"""Identify a product from a barcode: the registry first, then a public product database. A product
found there is added to the registry once (one record per physical product) and screened at once,
so the person who scanned it lands on a passport."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import audit
from app.models import Brand, Category, IdentificationRequest, Product, ProductAlias

from . import upcitemdb

QUOTA = text("select telcron_setting_int('identify.daily_quota', 20)")
# Category in the product database -> the registry's category code. First match wins.
CATEGORIES = [
    (r"blender", "blenders"), (r"refrigerat|fridge", "mini_fridges"),
    (r"air condition", "window_ac"), (r"charger|adapter|power bank|power supply", "power_adapters"),
    (r"phone", "smartphones"), (r"electronic|computer|camera|audio", "electronics"),
    (r"appliance|kitchen", "appliances"), (r"food|grocery|beverage", "food"),
]


def gtin14(code: str) -> str | None:
    """A UPC-A, EAN-8, EAN-13 or GTIN-14 as 14 digits, or None if it is not one (bad check digit)."""
    digits = re.sub(r"\D", "", code)
    if len(digits) not in (8, 12, 13, 14):
        return None
    digits = digits.zfill(14)
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(body))
    return digits if (10 - total % 10) % 10 == check else None


def category_code(path: str | None) -> str:
    for pattern, code in CATEGORIES:
        if re.search(pattern, path or "", re.I):
            return code
    return "household"


def slug(*parts: str) -> str:
    text_ = re.sub(r"[^a-z0-9]+", "-", " ".join(parts).lower()).strip("-")
    return text_[:80].strip("-")


async def _registry_hit(db: AsyncSession, gtin: str) -> Product | None:
    return (await db.execute(select(Product).join(ProductAlias, ProductAlias.product_id == Product.id)
                             .where(ProductAlias.alias_type == "gtin", ProductAlias.alias_value == gtin,
                                    Product.status == "active").limit(1))).scalar_one_or_none()


async def _add_to_registry(db: AsyncSession, gtin: str, item: dict[str, Any],
                           user_id: uuid.UUID | None) -> Product:
    brand_name = (item.get("brand") or "").strip() or None
    brand = None
    if brand_name:
        key = brand_name.lower()
        brand = (await db.execute(select(Brand).where(Brand.normalized_name == key))).scalar_one_or_none()
        if brand is None:
            brand = Brand(name=brand_name, normalized_name=key)
            db.add(brand)
            await db.flush()
    model = (item.get("model") or "").strip() or None
    model_norm = re.sub(r"[^A-Z0-9]", "", model.upper()) if model else None
    if brand and model_norm:  # the same physical product listed under another barcode
        existing = (await db.execute(select(Product).where(
            Product.brand_id == brand.id, Product.model_number_normalized == model_norm,
            Product.status == "active"))).scalar_one_or_none()
        if existing:
            db.add(ProductAlias(product_id=existing.id, alias_type="gtin", alias_value=gtin,
                                data_source_code="upcitemdb", confidence=Decimal("0.9")))
            return existing
    category = (await db.execute(select(Category).where(
        Category.code == category_code(item.get("category"))))).scalar_one()
    name = (item.get("title") or f"Product {gtin}").strip()[:300]
    product = Product(
        category_id=category.id, brand_id=brand.id if brand else None, canonical_name=name,
        model_number=model, model_number_normalized=model_norm or None,
        description=(item.get("description") or "").strip()[:2000] or None,
        identification_source="barcode", identity_confidence=Decimal("0.9"),
        public_slug=slug(brand_name or "", name[:50], gtin[-6:]) or f"product-{gtin}",
        created_by_user_id=user_id)
    db.add(product)
    await db.flush()
    db.add(ProductAlias(product_id=product.id, alias_type="gtin", alias_value=gtin,
                        data_source_code="upcitemdb", confidence=Decimal("0.9")))
    audit(db, action="product.identified", entity_type="product", entity_id=product.id,
          actor_user_id=user_id, changes={"gtin": gtin, "source": "upcitemdb"})
    return product


async def by_barcode(db: AsyncSession, code: str, user_id: uuid.UUID | None) -> dict[str, Any]:
    digits = re.sub(r"\D", "", code)
    if len(digits) not in (8, 12, 13, 14):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_barcode")
    known = await _registry_hit(db, digits.zfill(14))
    gtin = gtin14(code) or (digits.zfill(14) if known else None)
    if gtin is None:  # a misread scan: do not spend a lookup on it
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_barcode")
    if user_id is not None:
        since = datetime.now(UTC) - timedelta(days=1)
        used = await db.scalar(select(func.count()).select_from(IdentificationRequest).where(
            IdentificationRequest.user_id == user_id, IdentificationRequest.created_at >= since))
        if used >= await db.scalar(QUOTA):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "identify_quota_reached")
    request = IdentificationRequest(user_id=user_id, input_type="barcode", barcode_value=gtin)
    db.add(request)
    product = known
    created = False
    if product is not None:
        request.cache_hit = True
    else:
        try:
            item = await upcitemdb.lookup(gtin)
        except upcitemdb.LookupUnavailable as exc:
            request.status, request.completed_at = "failed", datetime.now(UTC)
            request.extracted = {"error": str(exc)[:300]}
            await db.commit()
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "lookup_unavailable") from exc
        if item is None:
            request.status, request.completed_at = "needs_input", datetime.now(UTC)
            await db.commit()
            raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_identified")
        request.extracted = {k: item.get(k) for k in ("title", "brand", "model", "category")}
        product = await _add_to_registry(db, gtin, item, user_id)
        created = product.current_passport_id is None
    request.status, request.resolved_product_id = "identified", product.id
    request.confidence = Decimal("1") if request.cache_hit else Decimal("0.9")
    request.completed_at = datetime.now(UTC)
    await db.flush()
    if created:  # screened now, so the person who scanned it sees a passport, not a blank page
        from app.modules.screening.service import screen_product
        await screen_product(db, product.id, "initial")
    return {"slug": product.public_slug, "name": product.canonical_name, "new": created}
