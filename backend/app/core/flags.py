"""Feature flags (WO-056, CT-001): unfinished features hide behind rows in `feature_flags`.

`is_enabled` is the one server-side reader; a flag with no row is off. A module hides an unfinished
route by answering 404 `not_found` while its flag is off. `rollout` is not evaluated in phase one.
"""

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeatureFlag

from .deps import Db


async def is_enabled(session: AsyncSession, code: str) -> bool:
    """True only when a row for `code` exists and is enabled."""
    return bool(await session.scalar(
        select(FeatureFlag.is_enabled).where(FeatureFlag.code == code)))


async def enabled_codes(session: AsyncSession) -> list[str]:
    return list((await session.scalars(
        select(FeatureFlag.code).where(FeatureFlag.is_enabled.is_(True))
        .order_by(FeatureFlag.code))).all())


class FlagsOut(BaseModel):
    flags: dict[str, bool]


router = APIRouter(tags=["platform"])


@router.get("/flags", response_model=FlagsOut)
async def list_flags(db: Db, response: Response) -> FlagsOut:
    """Public: the enabled flags, the same for every caller. Absent means off."""
    response.headers["Cache-Control"] = "public, max-age=60"
    return FlagsOut(flags=dict.fromkeys(await enabled_codes(db), True))
