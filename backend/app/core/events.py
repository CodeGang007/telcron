"""The outbox. Critical events are written in the same transaction as the data they describe;
the publisher (app/workers/publisher.py) is the only reader."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, OutboxEvent

# event_type -> job queue. An event type missing here is a bug the publisher reports loudly.
ROUTES: dict[str, str] = {
    "ProductIngested": "screening",
    "ReviewSubmitted": "screening",
    "HazardFlagConfirmed": "screening",
    "CoinsEarned": "coins",
    "PassportIssued": "alerts",
}
QUEUES = ("ingest", "media", "screening", "identity", "coins", "alerts")
DEAD_LETTER_KEY = "telcron:dead-letter"


def queue_name(queue: str) -> str:
    return f"telcron:queue:{queue}"


def emit(session: AsyncSession, aggregate_type: str, aggregate_id: uuid.UUID, event_type: str,
         payload: dict[str, Any] | None = None) -> OutboxEvent:
    if event_type not in ROUTES:
        raise ValueError(f"unrouted event type: {event_type}")
    event = OutboxEvent(aggregate_type=aggregate_type, aggregate_id=aggregate_id,
                        event_type=event_type, payload=payload or {})
    session.add(event)
    return event


def audit(session: AsyncSession, *, action: str, entity_type: str, entity_id: uuid.UUID | None,
          actor_user_id: uuid.UUID | None = None, actor_type: str | None = None,
          changes: dict[str, Any] | None = None) -> None:
    session.add(AuditLog(
        actor_type=actor_type or ("user" if actor_user_id else "system"),
        actor_user_id=actor_user_id, action=action, entity_type=entity_type,
        entity_id=entity_id, changes=changes,
    ))
