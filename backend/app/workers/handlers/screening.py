import uuid
from typing import Any

from app.core.db import SessionLocal
from app.core.redis import get_redis
from app.modules.screening.service import screen_product

# event -> screening_run_type; anything else re-screens an already screened product
RUN_TYPE = {"ProductIngested": "initial"}


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    product_id = uuid.UUID(payload["product_id"])
    async with SessionLocal() as db:
        await screen_product(db, product_id, RUN_TYPE.get(event_type, "rescreen"))
        await db.commit()
    await (await get_redis()).delete(f"telcron:passport:{product_id}")
