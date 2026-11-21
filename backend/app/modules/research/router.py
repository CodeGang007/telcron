from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import Db, Level1User
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
async def research_summary(id_or_slug: str, db: Db) -> dict:
    """What the recall databases and the web said about this product, with each source."""
    return await service.summary(db, await _product(db, id_or_slug))


@router.post("/products/{id_or_slug}/research", status_code=status.HTTP_202_ACCEPTED)
async def request_research(id_or_slug: str, db: Db, user: Level1User) -> dict:
    """Search again now. At most once a day per product, and within a daily budget."""
    product = await _product(db, id_or_slug)
    job = await service.request(db, product, user.id, trigger="admin" if user.role == "admin"
                                else "event")
    if job is None:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "research_not_due")
    return {"job_id": str(job.id), "status": job.status}


@router.get("/products/{id_or_slug}/marketplace")
async def marketplace(id_or_slug: str, db: Db,
                      country: str = Query("US", pattern=r"^[A-Z]{2}$")) -> dict:
    """Products like this one listed on the big marketplaces in the shopper's country, with links.
    Not checked by Telcron until a member asks."""
    product = await _product(db, id_or_slug)
    brand = await db.scalar(select(Brand.name).where(Brand.id == product.brand_id))
    return await market.listings(str(product.id), product.canonical_name, brand, country)


class CheckIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    url: str = Field(min_length=10, max_length=500)


@router.post("/products/{id_or_slug}/marketplace/check")
async def check_listing(id_or_slug: str, data: CheckIn, db: Db, user: Level1User) -> dict:
    """Add a marketplace listing to the registry, in this product's category, and research it."""
    from app.modules.catalogue.identify import CATEGORY_CODES, confirm
    product = await _product(db, id_or_slug)
    code = await db.scalar(select(Category.code).where(Category.id == product.category_id))
    code = code if code in CATEGORY_CODES else "household"
    words = data.title.split()
    return await confirm(db, {"name": data.title[:200], "brand": words[0][:120] if words else None,
                              "model": None, "category": code, "barcode": None,
                              "request_id": None}, user.id)
