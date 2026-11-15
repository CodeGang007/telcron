"""TelCoins. Every write goes through the database's `coin_*` functions (db/schema-next/
phase3_rules.sql): they lock the user's balance row, apply the limits, the daily cap, the
rapid-fire fraud hold and the level bonus, and keep `coin_balances` in step with the ledger.
This module never inserts into or updates the ledger itself."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import emit
from app.models import CoinLedgerEntry, ReviewTask, RewardLevel

EARN = text(
    "select coin_earn(cast(:user as uuid), cast(:rule as text), cast(:key as text), "
    "cast(:subject_type as text), cast(:subject_id as uuid))")


async def earn(db: AsyncSession, user_id: uuid.UUID, rule_code: str, *,
               subject_type: str | None = None, subject_id: uuid.UUID | None = None,
               idempotency_key: str) -> CoinLedgerEntry | None:
    """Award coins for a rule. Returns the new ledger entry, or None when nothing new was
    awarded: a limit was reached, the daily cap is used up, or this key was already used."""
    if (await db.execute(select(CoinLedgerEntry.id).where(
            CoinLedgerEntry.idempotency_key == idempotency_key))).first():
        return None
    entry_id = await db.scalar(EARN, {"user": user_id, "rule": rule_code, "key": idempotency_key,
                                      "subject_type": subject_type, "subject_id": subject_id})
    if entry_id is None:
        return None
    entry = await db.get(CoinLedgerEntry, entry_id)
    if entry.status == "pending":
        # The coins handler sweeps due entries; this event wakes it when this one becomes due.
        emit(db, "coin_ledger_entry", entry.id, "CoinsEarned",
             {"entry_id": str(entry.id), "not_before": entry.confirmable_at.isoformat()})
    elif entry.status == "frozen" and entry.fraud_hold_id is not None:
        await _queue_hold_review(db, entry.fraud_hold_id, user_id)
    return entry


async def _queue_hold_review(db: AsyncSession, hold_id: uuid.UUID, user_id: uuid.UUID) -> None:
    exists = (await db.execute(select(ReviewTask.id).where(
        ReviewTask.task_type == "fraud_hold", ReviewTask.subject_id == hold_id))).first()
    if not exists:
        db.add(ReviewTask(task_type="fraud_hold", subject_type="fraud_hold", subject_id=hold_id,
                          priority=1, payload={"user_id": str(user_id)}))


async def confirm_due(db: AsyncSession) -> int:
    """Confirm every pending entry whose review window has passed. Returns how many."""
    return int(await db.scalar(text("select coin_confirm_due()")))


async def level_for(db: AsyncSession, lifetime_earned: int) -> RewardLevel | None:
    return (await db.execute(
        select(RewardLevel).where(RewardLevel.min_lifetime_coins <= lifetime_earned)
        .order_by(RewardLevel.level.desc()).limit(1))).scalar_one_or_none()
