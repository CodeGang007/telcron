"""The API service. Same codebase as the Worker (app/workers/main.py); PostgreSQL is the truth."""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.core.redis import close_redis, get_redis
from app.modules.catalogue.router import router as catalogue
from app.modules.community.router import router as community
from app.modules.identity.router import router as identity
from app.modules.rewards.router import router as rewards
from app.modules.screening.router import router as screening
from app.modules.wallet.router import router as wallet
from app.workers.publisher import run_publisher


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = None
    if get_settings().run_outbox_publisher:
        task = asyncio.create_task(run_publisher())
    yield
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    await close_redis()
    await engine.dispose()


app = FastAPI(title="Telcron API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[get_settings().web_origin],
                   allow_methods=["*"], allow_headers=["*"])

# The route table of contents. Only tech-lead edits this list.
for router in (identity, catalogue, community, wallet, rewards, screening):
    app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["platform"])
async def health() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    await (await get_redis()).ping()
    return {"status": "ok", "version": get_settings().git_sha}
