from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.core.deps import Db, Level1User, OptionalUser
from app.core.paging import Offset, page

from . import identify as identify_service
from . import service

router = APIRouter(tags=["catalogue"])


class IdentifyIn(BaseModel):
    barcode: str = Field(min_length=6, max_length=40)  # digits as printed; spaces and dashes are fine


@router.get("/products")
async def search_products(db: Db, user: OptionalUser, response: Response, offset: Offset = 0,
                          q: str = Query("", max_length=200),
                          limit: int = Query(20, ge=1, le=50)) -> list[dict[str, Any]]:
    rows = await service.search(db, q, limit + 1, user.id if user else None, offset)
    return page(rows, limit, response)


@router.post("/identify")
async def identify(data: IdentifyIn, db: Db, user: OptionalUser) -> dict[str, Any]:
    """A scanned or typed barcode -> a product with a passport. Photo identification is not built."""
    return await identify_service.by_barcode(db, data.barcode, user.id if user else None)


class PhotoIn(BaseModel):
    image: str = Field(max_length=5_000_000)  # a data: URL, resized in the browser
    barcode: str | None = Field(None, max_length=40)


class ConfirmIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    brand: str | None = Field(None, max_length=120)
    model: str | None = Field(None, max_length=80)
    category: str
    barcode: str | None = Field(None, max_length=40)
    request_id: str | None = None


@router.post("/identify/photo")
async def identify_photo(data: PhotoIn, db: Db, user: Level1User) -> dict[str, Any]:
    """A suggestion of what a photographed product is, for the member to check. Stores nothing else."""
    return await identify_service.suggest_from_photo(db, data.image, data.barcode, user.id)


@router.post("/identify/confirm")
async def identify_confirm(data: ConfirmIn, db: Db, user: Level1User) -> dict[str, Any]:
    """Add a product a member has identified (from a photo or by hand) and screen it."""
    return await identify_service.confirm(db, data.model_dump(), user.id)


@router.get("/products/{id_or_slug}")
async def get_product(id_or_slug: str, db: Db) -> dict[str, Any]:
    product = await service.find_product(db, id_or_slug)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
    return await service.product_detail(db, product)


@router.get("/products/{id_or_slug}/passport")
async def get_passport(id_or_slug: str, db: Db) -> dict[str, Any]:
    product = await service.find_product(db, id_or_slug)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
    view = await service.passport_view(db, product)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "passport_not_issued")
    return view


@router.get("/stats")
async def stats(db: Db) -> dict[str, int]:
    """Counts for the home page. Public."""
    from sqlalchemy import text
    row = (await db.execute(text("""
        select (select count(*) from products where status = 'active'),
               (select count(*) from recalls where status = 'active'),
               (select count(*) from passports),
               (select count(*) from users where verification_level >= 1 and deleted_at is null),
               (select count(*) from reviews where status = 'published')"""))).one()
    return dict(zip(("products", "recalls", "passports", "members", "reviews"), map(int, row), strict=True))
