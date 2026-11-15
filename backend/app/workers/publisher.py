"""The event publisher: the only reader of outbox_events. Runs inside the API service.

Rows are claimed with SKIP LOCKED so several API tasks can run it. A row is marked published in
the same transaction that enqueued it; the job id is the event id, so a crash between enqueue and
commit re-enqueues the same id and Redis drops the duplicate.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.events import ROUTES, queue_name
from app.core.redis import get_redis
from app.models import OutboxEvent

log = logging.getLogger("telcron.publisher")
BATCH = 100
IDLE_SECONDS = 1.0


async def publish_once() -> int:
    redis = await get_redis()
    async with SessionLocal() as db:
        events = (await db.execute(
            select(OutboxEvent).where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at).limit(BATCH).with_for_update(skip_locked=True)
        )).scalars().all()
        for event in events:
            not_before = event.payload.get("not_before")
            await redis.enqueue_job(
                "handle", str(event.id), event.event_type, event.payload,
                _job_id=f"evt:{event.id}", _queue_name=queue_name(ROUTES[event.event_type]),
                _defer_until=datetime.fromisoformat(not_before) if not_before else None)
            event.published_at = datetime.now(UTC)
            event.attempts += 1
        await db.commit()
        return len(events)


async def run_publisher() -> None:
    while True:
        try:
            if await publish_once() < BATCH:
                await asyncio.sleep(IDLE_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Redis or the database is down: the rows wait in the table. Try again.
            log.exception("outbox publish failed")
            await asyncio.sleep(5)
