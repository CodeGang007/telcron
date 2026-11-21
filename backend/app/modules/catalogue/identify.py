"""Identify a product from a barcode: the registry first, then a public product database. A product
found there is added to the registry once (one record per physical product) and screened at once,
so the person who scanned it lands on a passport."""

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import audit
from app.models import (
    Brand,
    Category,
    IdentificationRequest,
    MediaAnnotation,
    MediaAsset,
    MediaBlob,
    Product,
    ProductAlias,
    ProductMedia,
)

from . import openfacts, photos, upcitemdb, vision

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


SAME_CORE = 0.75  # share of the core words two titles of one brand must have in common
COLOURS = set("""white black grey gray silver gold red blue green yellow orange pink purple violet
brown beige cream ivory navy teal azure rose clear transparent multicolour multicolor assorted
""".split())
VARIANT = re.compile(r"^(\d+([.,]\d+)?(ml|l|ltr|litre|liter|g|gm|kg|mg|oz|lb|cm|mm|m|in|inch|w|v|"
                     r"mah|gb|tb)|pack|packs|of|pcs|pieces|piece|set|size|colour|color|edition|"
                     r"new|the|and|with|for)$")
COUNT = re.compile(r"\b(pack|set|box|case) of \d+\b|\b\d+\s*(pieces|piece|pcs|pc|pack|ct|count)\b"
                   r"|\b\d+\s*x\b|\bx\s*\d+\b")


def core_words(name: str, brand: str | None) -> set[str]:
    """A title without its brand, colours, sizes and pack counts: what makes it this product
    rather than one of its variants."""
    skip = set(re.findall(r"[a-z0-9]+", (brand or "").lower()))
    return {w for w in re.findall(r"[a-z0-9]+(?:[.,]\d+)?[a-z]*", COUNT.sub(" ", name.lower()))
            if w not in skip and w not in COLOURS and not VARIANT.match(w)}


async def same_product(db: AsyncSession, brand: Brand | None, model_norm: str | None,
                       name: str) -> Product | None:
    """A product already in the registry that this one is, under another barcode (a colour, a
    size, a pack, another country's code). The same brand is required. Then: the same model number
    is the same product; two different model numbers never are; otherwise the core words of the
    titles must match closely."""
    if brand is None:
        return None
    if model_norm:
        hit = (await db.execute(select(Product).where(
            Product.brand_id == brand.id, Product.model_number_normalized == model_norm,
            Product.status == "active").limit(1))).scalar_one_or_none()
        if hit:
            return hit
    mine = core_words(name, brand.name)
    if len(mine) < 2:
        return None
    best, best_score = None, 0.0
    for product in (await db.execute(select(Product).where(
            Product.brand_id == brand.id, Product.status == "active").limit(300))).scalars():
        if model_norm and product.model_number_normalized \
                and product.model_number_normalized != model_norm:
            continue  # two model numbers that differ are two products
        theirs = core_words(product.canonical_name, brand.name)
        score = len(mine & theirs) / len(mine | theirs) if theirs else 0.0
        if score > best_score:
            best, best_score = product, score
    return best if best_score >= SAME_CORE else None


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
    name = (item.get("title") or f"Product {gtin}").strip()[:300]
    existing = await same_product(db, brand, model_norm, name)
    if existing:  # the same product under another barcode (a size, a pack, another country)
        if gtin and not await _registry_hit(db, gtin):
            db.add(ProductAlias(product_id=existing.id, alias_type="gtin", alias_value=gtin,
                                data_source_code=source, confidence=confidence))
        audit(db, action="product.barcode_linked", entity_type="product", entity_id=existing.id,
              actor_user_id=user_id, changes={"gtin": gtin, "source": source, "title": name})
        return existing
    code = item.get("category_code") or category_code(item.get("category"))
    category = (await db.execute(select(Category).where(Category.code == code))).scalar_one_or_none() \
        or (await db.execute(select(Category).where(Category.code == "household"))).scalar_one()
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
        await _first_look(db, product, user_id)
    return {"slug": product.public_slug, "name": product.canonical_name, "new": created}


async def _first_look(db: AsyncSession, product: Product, user_id: uuid.UUID | None) -> None:
    """A new product: screened now from what the registry knows, then researched in the Worker
    (recall databases and the web), which screens it again with what it found."""
    from app.modules.research.service import request
    from app.modules.screening.service import screen_product
    await screen_product(db, product.id, "initial")
    await request(db, product, user_id)


# ------------------------------------------------- a product no database knows: photo, then a person

MAX_PHOTO_BYTES = 3_500_000  # the provider takes at most 4 MB of base64
CATEGORY_CODES = ("blenders", "mini_fridges", "window_ac", "power_adapters", "smartphones",
                  "electronics", "appliances", "food", "household")


async def _keep_photo(db: AsyncSession, mime: str, body: bytes, user_id: uuid.UUID
                      ) -> MediaAsset | None:
    """Stored privately when a photo store is configured; one blob per distinct file."""
    if get_settings().media_store != "s3":
        return None
    digest = hashlib.sha256(body).digest()
    blob = (await db.execute(select(MediaBlob).where(MediaBlob.sha256 == digest))
            ).scalar_one_or_none()
    if blob is None:
        key = f"photos/{datetime.now(UTC):%Y/%m}/{uuid.uuid4().hex}.{mime.split('/')[1]}"
        await photos.store(key, mime, body)
        blob = MediaBlob(sha256=digest, kind="image", mime_type=mime, byte_size=len(body),
                         storage_key_original=key)
        db.add(blob)
        await db.flush()
    asset = MediaAsset(blob_id=blob.id, owner_user_id=user_id, visibility="private")
    db.add(asset)
    await db.flush()
    return asset


async def suggest_from_photo(db: AsyncSession, data_urls: list[str], barcode: str | None,
                             user_id: uuid.UUID) -> dict[str, Any]:
    """What the photos (up to four sides of one product) appear to show, and registry products
    that may be the same one. Nothing is added to the registry: a person confirms, corrects, or
    picks an existing product first."""
    decoded = []
    for data_url in data_urls[:4]:
        if len(data_url) > MAX_PHOTO_BYTES * 4 // 3 + 100:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "photo_unreadable")
        try:
            decoded.append(photos.decode(data_url))
        except photos.PhotoUnreadable as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "photo_unreadable") from exc
    assets = [a for mime, body in decoded if (a := await _keep_photo(db, mime, body, user_id))]
    asset = assets[0] if assets else None
    # With the photo kept it is an image request; without, a text one marked `from_photo`
    # (the database rightly wants an image request to keep its image).
    request = IdentificationRequest(
        user_id=user_id, input_type="image" if asset else "text",
        media_asset_id=asset.id if asset else None, text_query=None if asset else "(photo)",
        barcode_value=gtin14(barcode) if barcode else None)
    db.add(request)
    reading = photos.Reading()
    for i, (_, body) in enumerate(decoded):
        side = await photos.read(body)
        reading.lines += [line for line in side.lines if line not in reading.lines]
        reading.labels += [lb for lb in side.labels if lb[0] not in dict(reading.labels)]
        reading.error = reading.error or side.error
        if i < len(assets):
            for label, confidence in side.labels:
                db.add(MediaAnnotation(blob_id=assets[i].blob_id, label=label[:120],
                                       confidence=Decimal(str(confidence)),
                                       model_code="aws-rekognition-detect-labels"))
    vision_error = None
    try:
        answer = await vision.read_photo(data_urls, photos.hints(reading))
    except vision.VisionUnavailable as exc:
        vision_error = str(exc)[:300]
        if not reading.lines:
            request.status, request.completed_at = "failed", datetime.now(UTC)
            request.extracted = {"error": str(exc)[:300], "from_photo": True}
            await db.commit()
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                "photo_identification_unavailable") from exc
        # The model is down but the reader saw the pack: offer its largest line, unsure.
        answer = {"name": " ".join(reading.lines[:2])[:120], "confidence": 0.3,
                  "visible_text": " | ".join(reading.lines)}
    clean = {k: (str(answer.get(k)).strip()[:200] if answer.get(k) else None)
             for k in ("brand", "name", "model")}
    code = answer.get("category") if answer.get("category") in CATEGORY_CODES else "household"
    try:
        confidence = max(0.0, min(1.0, float(answer.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    request.status, request.completed_at = "needs_input", datetime.now(UTC)
    seen_text = str(answer.get("visible_text") or "")[:500]
    request.extracted = {**clean, "category": code, "visible_text": seen_text, "from_photo": True,
                         "photos": len(decoded), "asset_ids": [str(a.id) for a in assets],
                         "vision_error": vision_error,
                         "reader": {"lines": reading.lines[:10], "labels": reading.labels[:10],
                                    "error": reading.error}}
    query = " ".join(v for v in (clean["brand"], clean["name"], clean["model"]) if v)[:300]
    if request.input_type == "text":
        request.text_query = query or "(photo, nothing read)"
    request.confidence = Decimal(str(round(confidence, 3)))
    await db.flush()
    # The same product, if the registry has it: matched the way a new barcode is matched.
    likely = None
    brand = (await db.execute(select(Brand).where(Brand.normalized_name == clean["brand"].lower()))
             ).scalar_one_or_none() if clean["brand"] else None
    if clean["name"]:
        model_norm = re.sub(r"[^A-Z0-9]", "", clean["model"].upper()) if clean["model"] else None
        title = clean["name"] if not clean["brand"] or clean["name"].lower().startswith(
            clean["brand"].lower()) else f"{clean['brand']} {clean['name']}"
        hit = await same_product(db, brand, model_norm, title)
        likely = hit.public_slug if hit else None
    from .service import search
    similar = await search(db, " ".join(v for v in (clean["brand"], clean["name"]) if v), 4, None) \
        if clean["name"] or clean["brand"] else []
    return {"request_id": str(request.id), **clean, "category": code, "confidence": confidence,
            "similar": similar, "likely_same": likely, "read_text": reading.lines[:8],
            "looks_like": [n for n, _ in reading.labels[:5]]}


async def _attach_photo(db: AsyncSession, product: Product,
                        request: IdentificationRequest | None) -> None:
    """The member's confirmed photos become pictures of the product; the first is the cover if the
    product has none."""
    if request is None or request.media_asset_id is None:
        return
    ids = (request.extracted or {}).get("asset_ids") or [str(request.media_asset_id)]
    for n, asset_id in enumerate(ids):
        asset = await db.get(MediaAsset, uuid.UUID(asset_id))
        if asset is None or asset.owner_user_id != request.user_id or (await db.execute(
                select(ProductMedia).where(ProductMedia.product_id == product.id,
                                           ProductMedia.media_asset_id == asset.id))).first():
            continue
        asset.visibility = "public"
        cover = product.primary_media_id is None
        db.add(ProductMedia(product_id=product.id, media_asset_id=asset.id, sort_order=n,
                            role="primary" if cover else "packaging"))
        await db.flush()
        if cover:
            product.primary_media_id = asset.id


async def confirm(db: AsyncSession, data: dict[str, Any], user_id: uuid.UUID) -> dict[str, Any]:
    """A member says what the product is (from the photo's suggestion, corrected, or typed). It is
    added once, under its barcode if it has one, and screened at once."""
    gtin = gtin14(data["barcode"]) if data.get("barcode") else None
    if data.get("barcode") and gtin is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_barcode")
    request = None
    if data.get("request_id"):
        request = (await db.execute(select(IdentificationRequest).where(
            IdentificationRequest.id == data["request_id"],
            IdentificationRequest.user_id == user_id))).scalar_one_or_none()
    if gtin and (known := await _registry_hit(db, gtin)) is not None:
        await _resolve(db, request, known)
        return {"slug": known.public_slug, "name": known.canonical_name, "new": False,
                "linked": False}
    if data.get("existing"):  # the member says it is a product the registry already has
        from .service import find_product
        product = await find_product(db, data["existing"])
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
        if gtin:
            db.add(ProductAlias(product_id=product.id, alias_type="gtin", alias_value=gtin,
                                data_source_code="user_upload", confidence=Decimal("0.8")))
        audit(db, action="product.barcode_linked", entity_type="product", entity_id=product.id,
              actor_user_id=user_id, changes={"gtin": gtin, "by": "member"})
        await _resolve(db, request, product)
        return {"slug": product.public_slug, "name": product.canonical_name, "new": False,
                "linked": bool(gtin)}
    if data["category"] not in CATEGORY_CODES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "unknown_category")
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
        request.fallback_manufacturer, request.fallback_model = data.get("brand"), data.get("model")
    await _resolve(db, request, product)
    if created:
        await _first_look(db, product, user_id)
    return {"slug": product.public_slug, "name": product.canonical_name, "new": created,
            "linked": not created}


async def _resolve(db: AsyncSession, request: IdentificationRequest | None,
                   product: Product) -> None:
    if request is not None:
        request.status, request.resolved_product_id = "identified", product.id
        request.completed_at = request.completed_at or datetime.now(UTC)
    await _attach_photo(db, product, request)
    await db.flush()
