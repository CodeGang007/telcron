"""A risk event reaches everyone holding or watching the product.

Who is alerted is the database's decision: `telcron_fanout_risk_event` covers active wallet
holders with alerts on and watchers, respects a recall's geography, and is idempotent. This
handler then writes the in-app notification for each alert. Email delivery is WO-005."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exists, select, text

from app.core.db import SessionLocal
from app.models import Notification, UserRiskAlert

FANOUT = text("select telcron_fanout_risk_event(cast(:event as uuid))")


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    risk_event_id = uuid.UUID(payload["risk_event_id"])
    async with SessionLocal() as db:
        await db.execute(FANOUT, {"event": risk_event_id})
        alerts = (await db.execute(select(UserRiskAlert).where(
            UserRiskAlert.risk_event_id == risk_event_id,
            ~exists().where(Notification.user_risk_alert_id == UserRiskAlert.id)))).scalars().all()
        for alert in alerts:
            db.add(Notification(
                user_id=alert.user_id, channel="in_app", template_code="risk_event",
                user_risk_alert_id=alert.id, status="sent", sent_at=datetime.now(UTC),
                payload={"product_id": payload["product_id"],
                         "passport_id": payload["passport_id"]}))
        await db.commit()
