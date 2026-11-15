"""Integration tests run against a real PostgreSQL and Redis (docker compose), in their own
database `telcron_test` and Redis db 1. Nothing here touches the development data."""

import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://telcron:telcron@localhost:5436/telcron_test"
os.environ["REDIS_URL"] = "redis://localhost:6381/1"
os.environ["DEV_EXPOSE_CODES"] = "true"
os.environ["RUN_OUTBOX_PUBLISHER"] = "false"
os.environ["COIN_CONFIRM_DELAY_SECONDS"] = "0"
os.environ["AI_PROVIDER"] = "stub"
os.environ["ENV"] = "test"

import asyncpg  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database():
    admin = await asyncpg.connect("postgresql://telcron:telcron@localhost:5436/telcron")
    await admin.execute("DROP DATABASE IF EXISTS telcron_test WITH (FORCE)")
    await admin.execute("CREATE DATABASE telcron_test")
    await admin.close()

    from app import seed
    from app.core.db import SessionLocal, engine
    from app.core.redis import close_redis, get_redis
    from app.models import Base

    async with engine.begin() as conn:
        for ext in ("vector", "pg_trgm", "citext"):
            await conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await seed.reference(db)
        await seed.demo(db)
        await db.commit()
    await (await get_redis()).flushdb()
    yield
    await close_redis()
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db():
    from app.core.db import SessionLocal

    async with SessionLocal() as session:
        yield session
