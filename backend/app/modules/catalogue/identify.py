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

from . import openfacts, upcitemdb, vision

QUOTA = text("select telcron_setting_int('identify.daily_quota', 20)")
# Category in the product database -> the registry's category code. First match wins.
CATEGORIES = [
    (r"blender", "blenders"), (r"refrigerat|fridge", "mini_fridges"),
    (r"air condition", "window_ac"), (r"charger|adapter|power bank|power supply", "power_adapters"),
    (r"phone", "smartphones"), (r"electronic|computer|camera|audio", "electronics"),
    (r"appliance|kitchen", "appliances"), (r"food|grocery|beverage", "food"),
]


def _checks(digits: str) -> bool:
    digits = digits.zfill(14)
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits[:-1]))
    return (10 - total % 10) % 10 == int(digits[-1])


def upce_to_upca(code: str) -> str | None:
    """UPC-E, the short barcode on small packages, written out as the 12-digit UPC-A it stands for."""
    if len(code) == 7:  # printed without its number system digit
        code = "0" + code
    if len(code) != 8 or code[0] not in "01":
        return None
    ns, x, check = code[0], code[1:7], code[7]
    last = x[5]
    if last in "012":
        body = x[0:2] + last + "0000" + x[2:5]
    elif last == "3":
        body = x[0:3] + "00000" + x[3:5]
    elif last == "4":
        body = x[0:4] + "00000" + x[4]
    else:
        body = x[0:5] + "0000" + last
    return ns + body + check


def gtin14(code: str) -> str | None:
    """A UPC-A, UPC-E, EAN-8, EAN-13 or GTIN-14 as 14 digits, or None if it is not one."""
    digits = re.sub(r"\D", "", code)
    if len(digits) in (8, 12, 13, 14) and _checks(digits):
        return digits.zfill(14)
    expanded = upce_to_upca(digits) if len(digits) in (7, 8) else None
    if expanded and _checks(expanded):
        return expanded.zfill(14)
    return None


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


async def _add_to_registry(db: AsyncSession, gtin: str | None, item: dict[str, Any],
                           user_id: uuid.UUID | None, *, source: str = "upcitemdb",
                           how: str = "barcode", confidence: Decimal = Decimal("0.9")) -> Product:
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
                                data_source_code=source, confidence=confidence))
            return existing
    code = item.get("category_code") or category_code(item.get("category"))
    category = (await db.execute(select(Category).where(Category.code == code))).scalar_one_or_none() \
        or (await db.execute(select(Category).where(Category.code == "household"))).scalar_one()
    name = (item.get("title") or f"Product {gtin}").strip()[:300]
    tail = gtin[-6:] if gtin else uuid.uuid4().hex[:6]
    product = Product(
        category_id=category.id, brand_id=brand.id if brand else None, canonical_name=name,
        model_number=model, model_number_normalized=model_norm or None,
        description=(item.get("description") or "").strip()[:2000] or None,
        identification_source=how, identity_confidence=confidence,
        public_slug=slug(brand_name or "", name[:50], tail) or f"product-{tail}",
        created_by_user_id=user_id)
    db.add(product)
    await db.flush()
    if gtin:
        db.add(ProductAlias(product_id=product.id, alias_type="gtin", alias_value=gtin,
                            data_source_code=source, confidence=confidence))
    audit(db, action="product.identified", entity_type="product", entity_id=product.id,
          actor_user_id=user_id, changes={"gtin": gtin, "source": source, "how": how})
    return product


async def by_barcode(db: AsyncSession, code: str, user_id: uuid.UUID | None) -> dict[str, Any]:
    digits = re.sub(r"\D", "", code)
    if len(digits) not in (7, 8, 12, 13, 14):
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
        item, errors = None, []
        for client in (upcitemdb, openfacts):  # US retail first, then the worldwide open databases
            try:
                item = await client.lookup(gtin)
            except (upcitemdb.LookupUnavailable, openfacts.LookupUnavailable) as exc:
                errors.append(f"{client.__name__.rsplit('.', 1)[-1]}: {exc}"[:200])
                continue
            if item is not None:
                break
        if item is None and len(errors) == 2:
            request.status, request.completed_at = "failed", datetime.now(UTC)
            request.extracted = {"errors": errors}
            await db.commit()
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "lookup_unavailable")
        if item is None:
            request.status, request.completed_at = "needs_input", datetime.now(UTC)
            await db.commit()
            raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_identified")
        request.extracted = {k: item.get(k) for k in ("title", "brand", "model", "category")}
        product = await _add_to_registry(db, gtin, item, user_id,
                                         source="upcitemdb" if item.get("source") != "openfacts"
                                         else "telcron")
        created = product.current_passport_id is None
    request.status, request.resolved_product_id = "identified", product.id
    request.confidence = Decimal("1") if request.cache_hit else Decimal("0.9")
    request.completed_at = datetime.now(UTC)
    await db.flush()
    if created:  # screened now, so the person who scanned it sees a passport, not a blank page
        from app.modules.screening.service import screen_product
        await screen_product(db, product.id, "initial")
    return {"slug": product.public_slug, "name": product.canonical_name, "new": created}


# ------------------------------------------------- a product no database knows: photo, then a person

MAX_PHOTO_BYTES = 3_500_000  # the provider takes at most 4 MB of base64
CATEGORY_CODES = ("blenders", "mini_fridges", "window_ac", "power_adapters", "smartphones",
                  "electronics", "appliances", "food", "household")


async def suggest_from_photo(db: AsyncSession, data_url: str, barcode: str | None,
                             user_id: uuid.UUID) -> dict[str, Any]:
    """What the photo appears to show, and registry products that look like it. Nothing is stored
    except the attempt: a person confirms or corrects the suggestion first."""
    if not data_url.startswith("data:image/") or len(data_url) > MAX_PHOTO_BYTES * 4 // 3 + 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "photo_unreadable")
    # Recorded as a text identification: the database (rightly) wants an image request to keep its
    # image, and photos are not stored until the media pipeline exists. `extracted.from_photo` marks it.
    request = IdentificationRequest(user_id=user_id, input_type="text", text_query="(photo)",
                                    barcode_value=gtin14(barcode) if barcode else None)
    db.add(request)
    try:
        answer = await vision.read_photo(data_url)
    except vision.VisionUnavailable as exc:
        request.status, request.completed_at = "failed", datetime.now(UTC)
        request.extracted = {"error": str(exc)[:300], "from_photo": True}
        await db.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "photo_identification_unavailable") from exc
    clean = {k: (str(answer.get(k)).strip()[:200] if answer.get(k) else None)
             for k in ("brand", "name", "model")}
    code = answer.get("category") if answer.get("category") in CATEGORY_CODES else "household"
    try:
        confidence = max(0.0, min(1.0, float(answer.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    request.status, request.completed_at = "needs_input", datetime.now(UTC)
    seen_text = str(answer.get("visible_text") or "")[:500]
    request.extracted = {**clean, "category": code, "visible_text": seen_text, "from_photo": True}
    request.text_query = " ".join(v for v in (clean["brand"], clean["name"], clean["model"]) if v)[:300] \
        or "(photo, nothing read)"
    request.confidence = Decimal(str(round(confidence, 3)))
    await db.flush()
    from .service import search
    query = " ".join(v for v in (clean["brand"], clean["name"]) if v)
    similar = await search(db, query, 4, None) if query else []
    return {"request_id": str(request.id), **clean, "category": code, "confidence": confidence,
            "similar": similar}


async def confirm(db: AsyncSession, data: dict[str, Any], user_id: uuid.UUID) -> dict[str, Any]:
    """A member says what the product is (from the photo's suggestion, corrected, or typed). It is
    added once, under its barcode if it has one, and screened at once."""
    gtin = gtin14(data["barcode"]) if data.get("barcode") else None
    if data.get("barcode") and gtin is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_barcode")
    if gtin and (known := await _registry_hit(db, gtin)) is not None:
        return {"slug": known.public_slug, "name": known.canonical_name, "new": False}
    if data["category"] not in CATEGORY_CODES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown_category")
    request = None
    if data.get("request_id"):
        request = (await db.execute(select(IdentificationRequest).where(
            IdentificationRequest.id == data["request_id"],
            IdentificationRequest.user_id == user_id))).scalar_one_or_none()
    how = "ai_image" if request is not None else "manual"
    name, brand = data["name"].strip(), (data.get("brand") or "").strip()
    title = name if not brand or name.lower().startswith(brand.lower()) else f"{brand} {name}"
    item = {"title": title, "brand": brand or None, "model": data.get("model"),
            "category_code": data["category"]}
    # Confirmed by a verified member: above the identity floor, so it is screened; below a barcode
    # database's confidence, because one person said so.
    product = await _add_to_registry(db, gtin, item, user_id, source="user_upload", how=how,
                                     confidence=Decimal("0.8"))
    created = product.current_passport_id is None
    if request is not None:
        request.status, request.resolved_product_id = "identified", product.id
        request.fallback_manufacturer, request.fallback_model = data.get("brand"), data.get("model")
    await db.flush()
    if created:
        from app.modules.screening.service import screen_product
        await screen_product(db, product.id, "initial")
    return {"slug": product.public_slug, "name": product.canonical_name, "new": created}
