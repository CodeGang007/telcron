from fastapi import APIRouter, HTTPException, status

from app.core.deps import Db, Level1User
from app.modules.catalogue.service import find_product

from . import service

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
