import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import Db, require_role
from app.core.paging import Offset, page
from app.models import IngestionJob, User

from . import service

router = APIRouter(tags=["ingestion"])
Admin = Annotated[User, Depends(require_role("admin"))]


class IngestIn(BaseModel):
    source: Literal["cpsc"] = "cpsc"
    date_start: date | None = None
    date_end: date | None = None


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def start_ingestion(data: IngestIn, db: Db, admin: Admin) -> dict[str, Any]:
    """Queue a job; the Worker runs it. Follow it with GET /jobs/{id}."""
    params = {k: v.isoformat() for k, v in
              (("date_start", data.date_start), ("date_end", data.date_end)) if v}
    try:
        job = await service.create_job(db, data.source, params, "admin", admin.id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "bad_date_range") from exc
    await db.refresh(job)
    return service.job_view(job)


@router.get("/jobs")
async def list_jobs(db: Db, _: Admin, response: Response, offset: Offset = 0,
                    limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
    jobs = (await db.execute(select(IngestionJob).order_by(IngestionJob.created_at.desc())
                             .offset(offset).limit(limit + 1))).scalars()
    return [service.job_view(j) for j in page(list(jobs), limit, response)]


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, db: Db, _: Admin) -> dict[str, Any]:
    job = await db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job_not_found")
    return service.job_view(job)


@router.get("/recalls")
async def recalls(db: Db, response: Response, offset: Offset = 0, q: str = Query("", max_length=200),
                  limit: int = Query(30, ge=1, le=100)) -> list[dict[str, Any]]:
    """Recent recall notices, newest first. Public: no account needed."""
    return page(await service.recent_recalls(db, q, limit + 1, offset), limit, response)
