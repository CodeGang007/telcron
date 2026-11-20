import uuid
from typing import Any

from app.modules.ingestion.service import run_job


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    await run_job(uuid.UUID(payload["job_id"]))
