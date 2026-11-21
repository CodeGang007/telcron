"""Integration tests run against a real PostgreSQL and Redis.

The database is built from the designed schema in db/ — the migrations (all three phases), then the
core reference seed — in the order db/tests/conftest.py uses, as its own database inside the
local Postgres (`make up`). Nothing here touches the development data, and SQLAlchemy creates
nothing: if the application disagrees with the schema, these tests fail.
"""

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
TEST_DB = "telcron_api_test"


def _setting(name: str) -> str | None:
    """A value from the environment, else from the repository's .env file."""
    if os.environ.get(name):
        return os.environ[name]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return None


ADMIN_DSN = (os.environ.get("TELCRON_TEST_ADMIN_DSN") or _setting("DATABASE_URL")
             or "postgresql://telcron:telcron_dev@127.0.0.1:5433/telcron"
             ).replace("postgresql+asyncpg://", "postgresql://")
TEST_DSN = ADMIN_DSN.rsplit("/", 1)[0] + "/" + TEST_DB
REDIS = "/".join((_setting("REDIS_URL") or "redis://127.0.0.1:6381").split("/")[:3])

os.environ["DATABASE_URL"] = TEST_DSN
os.environ["REDIS_URL"] = REDIS + "/1"
os.environ["DEV_EXPOSE_CODES"] = "true"
os.environ["RUN_OUTBOX_PUBLISHER"] = "false"
os.environ["AI_PROVIDER"] = "stub"
os.environ["ENV"] = "test"

import asyncpg  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

FILES = (sorted((ROOT / "db" / "migrations").glob("*.sql"))
         + [ROOT / "db" / "seeds" / "001_core_reference.sql"])


def up_part(sql: str) -> str:
    """dbmate files: keep only the migrate:up section."""
    return sql.split("-- migrate:down", 1)[0]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def database():
    admin = await asyncpg.connect(ADMIN_DSN)
    await admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {TEST_DB}")
    await admin.close()
    conn = await asyncpg.connect(TEST_DSN)
    for path in FILES:
        try:
            await conn.execute(up_part(path.read_text()))
        except Exception as exc:  # surfaces which file broke
            raise RuntimeError(f"applying {path.relative_to(ROOT)} failed: {exc}") from exc
    # Tests confirm coins at once instead of waiting out the fraud-review window.
    await conn.execute("UPDATE coin_earn_rules SET confirmation_delay = interval '0'")
    await conn.close()

    from demo_catalogue import make_catalogue

    from app.core.db import SessionLocal, engine
    from app.core.redis import close_redis, get_redis

    async with SessionLocal() as db:
        await make_catalogue(db)
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


@pytest_asyncio.fixture(autouse=True)
async def no_outside_research(monkeypatch):
    """No test reaches a search engine, a registry or an image reader; a test that wants one
    replaces these."""
    from app.modules.catalogue import photos
    from app.modules.research import registries, web

    async def nothing(*args, **kwargs):
        return []

    async def no_registry(words, category, limit=5):
        return [], []

    async def unread(body):
        return photos.Reading()
    async def unknown_balance():
        return None
    from app.modules.research import service as research
    monkeypatch.setattr(web, "search", nothing)
    monkeypatch.setattr(research, "_searches_left", unknown_balance)
    monkeypatch.setattr(registries, "search", no_registry)
    monkeypatch.setattr(photos, "read", unread)


@pytest_asyncio.fixture(autouse=True)
async def no_open_facts(monkeypatch):
    """No test reaches the real Open Facts databases; a test that wants them replaces this."""
    from app.modules.catalogue import openfacts

    async def unknown(gtin):
        return None
    monkeypatch.setattr(openfacts, "lookup", unknown)
