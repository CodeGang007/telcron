"""The coin ledger. Every earn or spend is a new row; the balance moves in the same transaction."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import emit
from app.domain.coins import BURST_WINDOW_SECONDS, capped_amount, is_burst
from app.models import (
    CoinBalance,
    CoinEarnRule,
    CoinLedgerEntry,
    FraudHold,
    ReviewTask,
    RewardLevel,
)


async def _locked_balance(db: AsyncSession, user_id: uuid.UUID) -> CoinBalance:
    await db.execute(insert(CoinBalance).values(user_id=user_id).on_conflict_do_nothing())
    return (await db.execute(
        select(CoinBalance).where(CoinBalance.user_id == user_id).with_for_update()
    )).scalar_one()


async def earn(db: AsyncSession, user_id: uuid.UUID, rule_code: str, *,
               subject_type: str | None = None, subject_id: uuid.UUID | None = None,
               idempotency_key: str) -> CoinLedgerEntry | None:
    """Award coins as `pending`. Returns None when the rule is off, a limit is reached, the
    daily cap leaves nothing, or this idempotency key was already used."""
    rule = await db.get(CoinEarnRule, rule_code)
    if rule is None or not rule.is_active:
        return None
    if (await db.execute(select(CoinLedgerEntry.id).where(
            CoinLedgerEntry.idempotency_key == idempotency_key))).first():
        return None

    balance = await _locked_balance(db, user_id)  # serialises this user's earns
    base = select(func.count()).select_from(CoinLedgerEntry).where(
        CoinLedgerEntry.user_id == user_id, CoinLedgerEntry.rule_code == rule_code,
        CoinLedgerEntry.entry_type == "earn", CoinLedgerEntry.status != "reversed")
    if rule.lifetime_limit is not None and (await db.scalar(base)) >= rule.lifetime_limit:
        return None
    if rule.per_subject_limit is not None and subject_id is not None:
        if (await db.scalar(base.where(CoinLedgerEntry.subject_id == subject_id))
                ) >= rule.per_subject_limit:
            return None

    now = datetime.now(UTC)
    amount = int(rule.amount)
    if rule.counts_toward_daily_cap:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        capped_rules = select(CoinEarnRule.code).where(CoinEarnRule.counts_toward_daily_cap)
        today = await db.scalar(
            select(func.coalesce(func.sum(CoinLedgerEntry.amount), 0)).where(
                CoinLedgerEntry.user_id == user_id, CoinLedgerEntry.entry_type == "earn",
                CoinLedgerEntry.status != "reversed", CoinLedgerEntry.created_at >= day_start,
                CoinLedgerEntry.rule_code.in_(capped_rules)))
        amount = capped_amount(amount, int(today), True)
        if amount == 0:
            return None

    override = get_settings().coin_confirm_delay_seconds
    delay = timedelta(seconds=override) if override is not None else rule.confirmation_delay
    entry = CoinLedgerEntry(
        user_id=user_id, entry_type="earn", amount=amount, status="pending", rule_code=rule_code,
        subject_type=subject_type, subject_id=subject_id, idempotency_key=idempotency_key,
        confirmable_at=now + delay, status_changed_at=now)
    db.add(entry)
    balance.pending_balance += amount
    await db.flush()
    emit(db, "coin_ledger_entry", entry.id, "CoinsEarned",
         {"entry_id": str(entry.id), "not_before": entry.confirmable_at.isoformat()})
    return entry


async def confirm_entry(db: AsyncSession, entry_id: uuid.UUID) -> str:
    """Run the fraud rules, then confirm or freeze. Called by the coins handler."""
    entry = (await db.execute(select(CoinLedgerEntry).where(
        CoinLedgerEntry.id == entry_id).with_for_update())).scalar_one_or_none()
    if entry is None or entry.status != "pending":
        return "skipped"
    balance = await _locked_balance(db, entry.user_id)
    now = datetime.now(UTC)
    rule = await db.get(CoinEarnRule, entry.rule_code) if entry.rule_code else None

    open_hold = (await db.execute(select(FraudHold).where(
        FraudHold.user_id == entry.user_id, FraudHold.status == "open"))).scalars().first()
    if open_hold is None and rule is not None and rule.counts_toward_daily_cap:
        window = entry.created_at - timedelta(seconds=BURST_WINDOW_SECONDS)
        capped_rules = select(CoinEarnRule.code).where(CoinEarnRule.counts_toward_daily_cap)
        burst = await db.scalar(select(func.count()).select_from(CoinLedgerEntry).where(
            CoinLedgerEntry.user_id == entry.user_id, CoinLedgerEntry.entry_type == "earn",
            CoinLedgerEntry.rule_code.in_(capped_rules),
            CoinLedgerEntry.created_at > window, CoinLedgerEntry.created_at <= entry.created_at))
        if is_burst(int(burst)):
            open_hold = FraudHold(user_id=entry.user_id, rule_triggered="burst_20_in_5_minutes",
                                  reason=f"{burst} capped actions inside five minutes")
            db.add(open_hold)
            await db.flush()
            db.add(ReviewTask(task_type="fraud_hold", subject_type="fraud_hold",
                              subject_id=open_hold.id, priority=2,
                              payload={"user_id": str(entry.user_id)}))

    balance.pending_balance -= entry.amount
    entry.status_changed_at = now
    if open_hold is not None:
        entry.status, entry.fraud_hold_id = "frozen", open_hold.id
        balance.frozen_balance += entry.amount
        return "frozen"
    entry.status = "confirmed"
    balance.confirmed_balance += entry.amount
    balance.lifetime_earned += entry.amount
    return "confirmed"


async def level_for(db: AsyncSession, lifetime_earned: int) -> RewardLevel | None:
    return (await db.execute(
        select(RewardLevel).where(RewardLevel.min_lifetime_coins <= lifetime_earned)
        .order_by(RewardLevel.level.desc()).limit(1))).scalar_one_or_none()
