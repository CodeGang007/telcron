"""Notify everyone holding or watching a product whose passport changed. In-app only;
email delivery is WO-005."""

import uuid
from typing import Any

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Notification, ProductWatch, UserRiskAlert, WalletItem


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    product_id = uuid.UUID(payload["product_id"])
    risk_event_id = uuid.UUID(payload["risk_event_id"])
    passport_id = uuid.UUID(payload["passport_id"])
    async with SessionLocal() as db:
        holders = (await db.execute(select(WalletItem).where(
            WalletItem.product_id == product_id, WalletItem.deleted_at.is_(None),
            WalletItem.alerts_enabled))).scalars().all()
        targets: dict[uuid.UUID, uuid.UUID | None] = {i.user_id: i.id for i in holders}
        for user_id in (await db.execute(select(ProductWatch.user_id).where(
                ProductWatch.product_id == product_id))).scalars():
            targets.setdefault(user_id, None)
        for user_id, wallet_item_id in targets.items():
            alert = UserRiskAlert(user_id=user_id, risk_event_id=risk_event_id,
                                  wallet_item_id=wallet_item_id)
            db.add(alert)
            await db.flush()
            db.add(Notification(user_id=user_id, channel="in_app",
                                template_code="passport_changed", user_risk_alert_id=alert.id,
                                payload={"product_id": str(product_id),
                                         "passport_id": str(passport_id)}, status="sent"))
        await db.commit()
