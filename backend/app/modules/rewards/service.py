"""TelCoins. Every write goes through the database's `coin_*` functions
(db/migrations/20261122130300_phase3_rules.sql; coin_refund_redemption in
20261122140000_redemptions_phase_one.sql): they lock the user's balance row, apply the limits,
the daily cap, the rapid-fire fraud hold and the level bonus, and keep `coin_balances` in step
with the ledger. This module never inserts into or updates the ledger itself."""

import uuid
from datetime import UTC, datetime

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


# ---------------------------------------------------------------- streaks, badges, the store

LEVEL_BADGES = {2: "inspector", 3: "analyst", 4: "expert", 5: "master"}
REDEEM = text("select coin_redeem(cast(:user as uuid), cast(:item as text), cast(:key as text), "
              "cast(:product as uuid))")


async def daily_check_in(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Called on sign-in. The first sign-in of a day pays the streak rule; after seven days in a row
    it pays the bigger one. Returns the streak length in days."""
    today = (await db.scalar(text("select current_date")))
    inserted = (await db.execute(text(
        "insert into user_daily_logins (user_id, login_date) values (:u, current_date) "
        "on conflict do nothing returning 1"), {"u": user_id})).first()
    streak = int(await db.scalar(text("""
        with d as (select login_date, login_date - (row_number() over (order by login_date))::int as g
                     from user_daily_logins where user_id = :u)
        select count(*) from d where g = (select g from d where login_date = current_date)"""),
        {"u": user_id}) or 0)
    if inserted and await db.scalar(text("select verification_level >= 1 from users where id = :u"),
                                    {"u": user_id}):
        rule = "login_streak_7plus" if streak >= 7 else "login_streak"
        await earn(db, user_id, rule, idempotency_key=f"daily:{user_id}:{today}")
    return streak


async def streak_of(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(await db.scalar(text("""
        with d as (select login_date, login_date - (row_number() over (order by login_date))::int as g
                     from user_daily_logins where user_id = :u)
        select count(*) from d where g = (select g from d order by login_date desc limit 1)
          and (select max(login_date) from d) >= current_date - 1"""), {"u": user_id}) or 0)


async def award_level_badges(db: AsyncSession, user_id: uuid.UUID, level: int) -> None:
    for at, code in LEVEL_BADGES.items():
        if level >= at:
            await db.execute(text("insert into user_badges (user_id, badge_code) values (:u, :b) "
                                  "on conflict do nothing"), {"u": user_id, "b": code})


REFUND = text("select coin_refund_redemption(cast(:redemption as uuid), cast(:reason as text))")
# Phase one fulfils two kinds, watchlist_slots and pdf_report (tech doc §2.2, §9.4, D13). The database
# keeps every other item off sale; should one come back on sale before its fulfilment is built, it is
# refunded, not left waiting.


async def redeem(db: AsyncSession, user_id: uuid.UUID, item_code: str, key: str,
                 product_id: uuid.UUID | None) -> uuid.UUID:
    """Spend confirmed coins on a catalogue item and fulfil it at once. An item this service cannot
    fulfil is refunded in the same transaction and comes back `refunded`: no redemption is ever left
    `processing`. The caller must let that transaction commit (do not raise), or the refund is lost
    along with the spend."""
    from fastapi import HTTPException
    from fastapi import status as http
    from sqlalchemy.exc import DBAPIError

    from app.models import Redemption, RedemptionItem, UserEntitlement
    item = await db.get(RedemptionItem, item_code)
    if item is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND, "item_not_found")
    if item.fulfilment_type == "pdf_report" and product_id is None:
        raise HTTPException(http.HTTP_422_UNPROCESSABLE_ENTITY, "product_required")
    try:
        async with db.begin_nested():
            redemption_id = await db.scalar(REDEEM, {"user": user_id, "item": item_code,
                                                     "key": key, "product": product_id})
    except DBAPIError as exc:
        # TC011 is both coin_spend's "insufficient" and coin_redeem's "unknown or inactive item":
        # the database decides what is on sale, so anything else under TC011 is off sale.
        if "insufficient confirmed TelCoins" in str(exc):
            raise HTTPException(http.HTTP_409_CONFLICT, "not_enough_coins") from exc
        if getattr(exc.orig, "sqlstate", None) == "TC011":
            raise HTTPException(http.HTTP_404_NOT_FOUND, "item_not_found") from exc
        raise
    redemption = await db.get(Redemption, redemption_id)
    if redemption.status == "processing":
        now = datetime.now(UTC)
        if item.fulfilment_type == "watchlist_slots":
            db.add(UserEntitlement(user_id=user_id, source="redemption", redemption_id=redemption.id,
                                   entitlement=item.fulfilment_type, quantity=item.quantity,
                                   ends_at=now + item.duration if item.duration else None))
            redemption.status, redemption.fulfilled_at = "fulfilled", now
        elif item.fulfilment_type == "pdf_report":
            redemption.fulfilment = {"report": f"/products/{product_id}/report"}
            redemption.status, redemption.fulfilled_at = "fulfilled", now
        else:
            await db.flush()
            await db.scalar(REFUND, {"redemption": redemption.id,
                                     "reason": f"{item.fulfilment_type} is not fulfilled yet"})
            await db.refresh(redemption)  # the function set `refunded` behind the session
    return redemption.id


async def report_entitlement(db: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID):
    """The caller's most recent fulfilled hazard-report redemption for this product, or None
    (CT-002). Only the caller's own rows are read; a refunded, failed or processing one does not count.
    Matching is on the item's fulfilment type, not its code."""
    from app.models import Redemption, RedemptionItem
    return (await db.execute(
        select(Redemption.id, Redemption.fulfilled_at)
        .join(RedemptionItem, RedemptionItem.code == Redemption.item_code)
        .where(Redemption.user_id == user_id, Redemption.product_id == product_id,
               Redemption.status == "fulfilled", RedemptionItem.fulfilment_type == "pdf_report")
        .order_by(Redemption.fulfilled_at.desc().nulls_last(), Redemption.created_at.desc())
        .limit(1))).first()
