from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.deps import Db, OptionalUser

from . import service

router = APIRouter(tags=["catalogue"])


class IdentifyIn(BaseModel):
    barcode: str = Field(min_length=6, max_length=32, pattern=r"^[0-9A-Za-z-]+$")


@router.get("/products")
async def search_products(db: Db, user: OptionalUser, q: str = Query("", max_length=200),
                          limit: int = Query(20, ge=1, le=50)) -> list[dict[str, Any]]:
    return await service.search(db, q, limit, user.id if user else None)


@router.post("/identify")
async def identify(data: IdentifyIn, db: Db, user: OptionalUser) -> dict[str, Any]:
    """Barcode only. Photo identification needs the media pipeline and Titan vectors (WO-004)."""
    results = await service.search(db, data.barcode, 1, user.id if user else None)
    if not results:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_identified")
    return results[0]


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
