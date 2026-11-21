from datetime import UTC, datetime

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.deps import Db, Level1User
from app.core.paging import Offset, page
from app.models import CoinBalance, CoinLedgerEntry, RewardLevel, User

from . import service

router = APIRouter(tags=["rewards"])


class LevelOut(BaseModel):
    level: int
    title: str
    next_title: str | None
    next_at: int | None


class CoinsOut(BaseModel):
    confirmed: int
    pending: int
    frozen: int
    lifetime_earned: int
    level: LevelOut | None


class LedgerEntryOut(BaseModel):
    id: str
    entry_type: str
    amount: int
    status: str
    rule_code: str | None
    created_at: datetime


class LeaderRow(BaseModel):
    rank: int
    display_name: str
    coins: int


@router.get("/coins", response_model=CoinsOut)
async def get_coins(db: Db, user: Level1User) -> CoinsOut:
    bal = await db.get(CoinBalance, user.id)
    lifetime = int(bal.lifetime_earned) if bal else 0
    lvl = await service.level_for(db, lifetime)
    level_out = None
    if lvl is not None:
        nxt = (await db.execute(select(RewardLevel).where(RewardLevel.level > lvl.level)
                                .order_by(RewardLevel.level).limit(1))).scalar_one_or_none()
        level_out = LevelOut(level=lvl.level, title=lvl.title,
                             next_title=nxt.title if nxt else None,
                             next_at=int(nxt.min_lifetime_coins) if nxt else None)
    return CoinsOut(confirmed=int(bal.confirmed_balance) if bal else 0,
                    pending=int(bal.pending_balance) if bal else 0,
                    frozen=int(bal.frozen_balance) if bal else 0,
                    lifetime_earned=lifetime, level=level_out)


@router.get("/coins/history", response_model=list[LedgerEntryOut])
async def coin_history(db: Db, user: Level1User, response: Response, offset: Offset = 0,
                       limit: int = Query(50, ge=1, le=100)) -> list[LedgerEntryOut]:
    rows = (await db.execute(select(CoinLedgerEntry).where(CoinLedgerEntry.user_id == user.id)
                             .order_by(CoinLedgerEntry.created_at.desc())
                             .offset(offset).limit(limit + 1))).scalars()
    rows = page(list(rows), limit, response)
    return [LedgerEntryOut(id=str(r.id), entry_type=r.entry_type, amount=int(r.amount),
                           status=r.status, rule_code=r.rule_code, created_at=r.created_at)
            for r in rows]


@router.get("/leaderboard", response_model=list[LeaderRow])
async def leaderboard(db: Db, limit: int = Query(20, ge=1, le=100)) -> list[LeaderRow]:
    """Top contributors this month: confirmed coins earned since the first of the month."""
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    coins = func.sum(CoinLedgerEntry.amount).label("coins")
    rows = (await db.execute(
        select(User.display_name, coins).join(CoinLedgerEntry, CoinLedgerEntry.user_id == User.id)
        .where(CoinLedgerEntry.entry_type.in_(("earn", "level_bonus")),
               CoinLedgerEntry.status == "confirmed",
               CoinLedgerEntry.created_at >= month_start)
        .group_by(User.id).order_by(coins.desc(), User.created_at).limit(limit))).all()
    return [LeaderRow(rank=i + 1, display_name=r[0], coins=int(r[1])) for i, r in enumerate(rows)]


ICON = {"review": "message-square", "first_reviewer": "sparkles", "photo": "camera",
        "hazard_flag_confirmed": "shield-alert", "fact_verification": "badge-check",
        "login_streak": "flame", "login_streak_7plus": "flame", "referral": "users",
        "level1_verified": "user-check", "level2_verified": "id-card"}
WHAT = {"review": "Review a product you own", "first_reviewer": "Be the first to review a product",
        "photo": "Add a photo to a review", "hazard_flag_confirmed": "Report a hazard that is confirmed",
        "fact_verification": "Correct a product fact", "login_streak": "Sign in each day",
        "login_streak_7plus": "Sign in 7 days in a row", "referral": "Invite a friend who verifies",
        "level1_verified": "Verify your email and phone", "level2_verified": "Verify your identity"}


@router.get("/rewards")
async def rewards_overview(db: Db, user: Level1User) -> dict:
    """Everything the rewards page shows, in one call."""
    from app.models import Badge, CoinEarnRule, RedemptionItem, UserBadge
    bal = await db.get(CoinBalance, user.id)
    lifetime = int(bal.lifetime_earned) if bal else 0
    lvl = await service.level_for(db, lifetime)
    if lvl:
        await service.award_level_badges(db, user.id, lvl.level)
    levels = (await db.execute(select(RewardLevel).order_by(RewardLevel.level))).scalars().all()
    rules = (await db.execute(select(CoinEarnRule).where(CoinEarnRule.is_active)
                              .order_by(CoinEarnRule.amount))).scalars().all()
    items = (await db.execute(select(RedemptionItem).where(RedemptionItem.is_active)
                              .order_by(RedemptionItem.cost_coins))).scalars().all()
    earned = {b: at for b, at in (await db.execute(select(UserBadge.badge_code, UserBadge.awarded_at)
                                                  .where(UserBadge.user_id == user.id))).all()}
    badges = (await db.execute(select(Badge).order_by(Badge.code))).scalars().all()
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    coins = func.sum(CoinLedgerEntry.amount)
    board = (await db.execute(
        select(CoinLedgerEntry.user_id, coins.label("c")).where(
            CoinLedgerEntry.entry_type.in_(("earn", "level_bonus")),
            CoinLedgerEntry.status == "confirmed", CoinLedgerEntry.created_at >= month_start)
        .group_by(CoinLedgerEntry.user_id).order_by(coins.desc()))).all()
    rank = next((i + 1 for i, r in enumerate(board) if r[0] == user.id), None)
    return {
        "balance": {"confirmed": int(bal.confirmed_balance) if bal else 0,
                    "pending": int(bal.pending_balance) if bal else 0,
                    "frozen": int(bal.frozen_balance) if bal else 0, "lifetime_earned": lifetime},
        "level": lvl.level if lvl else 1,
        "levels": [{"level": x.level, "title": x.title, "min": int(x.min_lifetime_coins),
                    "bonus_pct": float(x.earn_bonus_pct), "perks": x.perks} for x in levels],
        "streak_days": await service.streak_of(db, user.id),
        "rank": rank, "ranked": len(board),
        "ways_to_earn": [{"code": r.code, "amount": int(r.amount), "icon": ICON.get(r.code, "coins"),
                          "label": WHAT.get(r.code, r.code.replace("_", " ")),
                          "capped": r.counts_toward_daily_cap} for r in rules],
        "badges": [{"code": b.code, "name": b.name, "earned_at": earned[b.code].isoformat()
                    if b.code in earned else None} for b in badges],
        "store": [{"code": i.code, "name": i.name, "cost": int(i.cost_coins),
                   "kind": i.fulfilment_type, "needs_product": i.fulfilment_type == "pdf_report"}
                  for i in items],
    }


class RedeemIn(BaseModel):
    item_code: str
    product: str | None = None
    request_id: str  # one per click: a retried request spends once


@router.post("/redemptions", status_code=201)
async def redeem(data: RedeemIn, db: Db, user: Level1User) -> dict:
    from app.modules.catalogue.service import find_product
    product = await find_product(db, data.product) if data.product else None
    if data.product and product is None:
        from fastapi import HTTPException
        raise HTTPException(404, "product_not_found")
    redemption_id = await service.redeem(db, user.id, data.item_code,
                                         f"{user.id}:{data.request_id}"[:120],
                                         product.id if product else None)
    from app.models import Redemption
    r = await db.get(Redemption, redemption_id)
    return {"id": str(r.id), "status": r.status, "item": r.item_code,
            "report": f"/products/{product.public_slug}/report" if product else None}
