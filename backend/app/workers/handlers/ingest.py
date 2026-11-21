import uuid
from typing import Any

from app.modules.ingestion.service import run_job
from app.modules.research import service as research


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    if event_type == "ResearchRequested":
        await research.run(uuid.UUID(payload["job_id"]))
        return
    await run_job(uuid.UUID(payload["job_id"]))
