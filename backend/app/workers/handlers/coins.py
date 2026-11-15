"""Confirms coins whose fraud-review window has passed.

`coin_confirm_due` sweeps every due entry of every user, so one run covers the entry that woke
this job and any other that became due meanwhile. Running it twice is harmless."""

from typing import Any

from app.core.db import SessionLocal
from app.modules.rewards.service import confirm_due


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    async with SessionLocal() as db:
        await confirm_due(db)
        await db.commit()
