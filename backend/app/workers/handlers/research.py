import uuid
from typing import Any

from app.modules.research import service


async def handle(event_type: str, payload: dict[str, Any]) -> None:
    await service.run(uuid.UUID(payload["job_id"]))
