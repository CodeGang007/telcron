from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import Db, Level1User, OptionalUser
from app.models import Brand, Category
from app.modules.catalogue.service import find_product

from . import market, service

router = APIRouter(tags=["research"])


async def _product(db, id_or_slug: str):
    product = await find_product(db, id_or_slug)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
    return product


@router.get("/products/{id_or_slug}/research")
async def research_summary(id_or_slug: str, db: Db, user: OptionalUser) -> dict:
    """What the recall databases and the web said about this product, with each source. Anyone
    may read it; only a signed-in view asks the search provider for its balance (DEF-042)."""
    return await service.summary(db, await _product(db, id_or_slug), signed_in=user is not None)


@router.post("/products/{id_or_slug}/research", status_code=status.HTTP_202_ACCEPTED)
async def request_research(id_or_slug: str, db: Db, user: Level1User) -> dict:
    """Search again now. At most once a day per product, and within a daily budget."""
    product = await _product(db, id_or_slug)
    admin = user.role == "admin"
    job = await service.request(db, product, user.id, trigger="admin" if admin else "event")
    if job is None:
        reason = (None if admin else await service.user_blocked(db, user.id)) \
            or await service.blocked(db, product) or "research_not_due"
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, reason)
    return {"job_id": str(job.id), "status": job.status}


@router.get("/products/{id_or_slug}/marketplace")
async def marketplace(id_or_slug: str, db: Db, user: OptionalUser,
                      country: str = Query("US", pattern=r"^[A-Z]{2}$")) -> dict:
    """Products like this one listed on the big marketplaces in the shopper's country, with links.
    Not checked by Telcron until a member asks. Anyone sees what is cached; only a verified member
    (Level 1, as for research) starts a new search (DEF-042)."""
    product = await _product(db, id_or_slug)
    brand = await db.scalar(select(Brand.name).where(Brand.id == product.brand_id))
    refused = "not_authenticated" if user is None else \
        "verification_level_1_required" if user.verification_level < 1 else None
    return await market.listings(str(product.id), product.canonical_name, brand, country, refused)


class CheckIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    url: str = Field(min_length=10, max_length=500)


@router.post("/products/{id_or_slug}/marketplace/check")
async def check_listing(id_or_slug: str, data: CheckIn, db: Db, user: Level1User) -> dict:
    """Add a marketplace listing to the registry, in this product's category, and research it.
    Only a listing Telcron showed for this product, under the title it showed (DEF-049)."""
    from app.modules.catalogue.identify import CATEGORY_CODES, confirm
    product = await _product(db, id_or_slug)
    listing = await market.cached_listing(str(product.id), data.url)
    if listing is None or listing.get("title") != data.title:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "listing_not_found")
    code = await db.scalar(select(Category.code).where(Category.id == product.category_id))
    code = code if code in CATEGORY_CODES else "household"
    title = str(listing["title"])
    words = title.split()
    return await confirm(db, {"name": title[:200], "brand": words[0][:120] if words else None,
                              "model": None, "category": code, "barcode": None,
                              "request_id": None}, user.id)
