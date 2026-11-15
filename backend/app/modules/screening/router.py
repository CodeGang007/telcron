import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import Db, require_role
from app.core.redis import get_redis
from app.models import Product, User

from . import service

router = APIRouter(tags=["screening"])
Staff = Annotated[User, Depends(require_role("admin", "moderator"))]


class ScreenIn(BaseModel):
    product_id: uuid.UUID


class ScreenOut(BaseModel):
    passport_id: str
    version: int
    status_badge: str
    trust_score: float | None


class ReviewTaskOut(BaseModel):
    id: str
    task_type: str
    subject_type: str
    subject_id: str
    status: str
    priority: int
    payload: dict[str, Any]
    created_at: datetime


@router.post("/screenings", response_model=ScreenOut, status_code=status.HTTP_201_CREATED)
async def screen_now(data: ScreenIn, db: Db, _: Staff) -> ScreenOut:
    """Screen a product now. Staff only until business API keys exist (WO-008, DEF-002)."""
    if await db.get(Product, data.product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product_not_found")
    passport = await service.screen_product(db, data.product_id, "manual")
    await db.commit()
    await (await get_redis()).delete(f"telcron:passport:{data.product_id}")
    return ScreenOut(passport_id=str(passport.id), version=passport.version,
                     status_badge=passport.status_badge,
                     trust_score=float(passport.trust_score)
                     if passport.trust_score is not None else None)


@router.get("/review-tasks", response_model=list[ReviewTaskOut])
async def review_tasks(db: Db, _: Staff) -> list[ReviewTaskOut]:
    return [ReviewTaskOut(id=str(t.id), task_type=t.task_type, subject_type=t.subject_type,
                          subject_id=str(t.subject_id), status=t.status, priority=t.priority,
                          payload=t.payload, created_at=t.created_at)
            for t in await service.open_review_tasks(db)]
