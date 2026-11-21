import uuid
from typing import Any

from app.core.db import SessionLocal
from app.modules.assistant import embedder
from app.modules.assistant.index import index_product, index_recalls


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    """A product's vectors, then a few recalls without one. With no embedder configured there is
    nothing to do; an embedder that is down raises, so the job is retried."""
    if not embedder.enabled():
        return
    async with SessionLocal() as db:
        await index_product(db, uuid.UUID(payload["product_id"]))
        await index_recalls(db, 20)
        await db.commit()
