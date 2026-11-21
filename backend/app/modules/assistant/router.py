from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import CurrentUser, Db
from app.modules.catalogue.service import find_product

from . import chat

router = APIRouter(tags=["assistant"])


class AskIn(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    thread_id: str | None = None


async def _product(db, id_or_slug: str):
    product = await find_product(db, id_or_slug)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
    return product


@router.get("/products/{id_or_slug}/assistant")
async def conversation(id_or_slug: str, db: Db, user: CurrentUser) -> dict:
    """The member's latest conversation about this product (the assistant's memory)."""
    return await chat.latest(db, user.id, (await _product(db, id_or_slug)).id)


@router.post("/products/{id_or_slug}/assistant")
async def ask(id_or_slug: str, data: AskIn, db: Db, user: CurrentUser) -> dict:
    """Ask about this product. Answers come only from what Telcron holds about it, with sources."""
    return await chat.ask(db, user.id, await _product(db, id_or_slug), data.message.strip(),
                          data.thread_id)
