from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.deps import Db, Level1User
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
async def coin_history(db: Db, user: Level1User,
                       limit: int = Query(50, ge=1, le=100)) -> list[LedgerEntryOut]:
    rows = (await db.execute(select(CoinLedgerEntry).where(CoinLedgerEntry.user_id == user.id)
                             .order_by(CoinLedgerEntry.created_at.desc()).limit(limit))).scalars()
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
