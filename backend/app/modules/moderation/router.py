import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.deps import Db, require_role
from app.models import User

from . import service

router = APIRouter(tags=["moderation"])
Staff = Annotated[User, Depends(require_role("admin", "moderator"))]


class ResolveIn(BaseModel):
    decision: Literal["confirm", "reject", "dismiss"]
    note: str | None = Field(None, max_length=1000)


@router.get("/review-tasks")
async def review_tasks(db: Db, _: Staff,
                       limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
    """The open queue, most urgent first."""
    return await service.list_tasks(db, limit)


@router.post("/review-tasks/{task_id}/claim")
async def claim(task_id: uuid.UUID, db: Db, staff: Staff) -> dict[str, Any]:
    return await service.describe(db, await service.claim(db, task_id, staff))


@router.post("/review-tasks/{task_id}/resolve")
async def resolve(task_id: uuid.UUID, data: ResolveIn, db: Db, staff: Staff) -> dict[str, Any]:
    task = await service.resolve(db, task_id, staff, data.decision, data.note)
    return await service.describe(db, task)
