import uuid
from typing import Any

from app.core.db import SessionLocal
from app.modules.rewards.service import confirm_entry


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    async with SessionLocal() as db:
        await confirm_entry(db, uuid.UUID(payload["entry_id"]))
        await db.commit()
