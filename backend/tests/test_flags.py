"""Feature flags (WO-056, CT-001): a flag is on only when its row says so; the list is public."""

import uuid

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.flags import is_enabled
from app.core.flags import router as flags_router
from app.models import FeatureFlag

API = "/api/v1"


@pytest_asyncio.fixture
async def flags_client():
    """The flags router on its own app until tech-lead lists it in app/main.py."""
    app = FastAPI()
    app.include_router(flags_router, prefix=API)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def two_flags(db):
    """One enabled and one disabled flag, unique to this test (the table is shared)."""
    on, off = f"test_on_{uuid.uuid4().hex[:8]}", f"test_off_{uuid.uuid4().hex[:8]}"
    db.add_all([FeatureFlag(code=on, is_enabled=True), FeatureFlag(code=off, is_enabled=False)])
    await db.commit()
    yield on, off
    await db.execute(delete(FeatureFlag).where(FeatureFlag.code.in_([on, off])))
    await db.commit()


async def test_an_enabled_flag_is_on(db, two_flags):
    assert await is_enabled(db, two_flags[0]) is True


async def test_a_disabled_flag_is_off(db, two_flags):
    assert await is_enabled(db, two_flags[1]) is False


async def test_a_flag_with_no_row_is_off(db):
    assert await is_enabled(db, f"never_created_{uuid.uuid4().hex[:8]}") is False


async def test_the_list_holds_only_enabled_flags(flags_client, two_flags):
    on, off = two_flags
    r = await flags_client.get(f"{API}/flags")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"flags"}
    assert body["flags"][on] is True
    assert off not in body["flags"]
    assert all(value is True for value in body["flags"].values())


async def test_the_list_needs_no_account_and_is_cacheable_for_a_minute(flags_client):
    r = await flags_client.get(f"{API}/flags")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=60"
