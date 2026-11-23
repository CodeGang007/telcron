"""`GET /products?screened=true` (CT-003 §E, DEF-121): only products whose current passport is tier 2,
for the home page's "Recently screened". Without it the list is what it always was."""

import uuid

from helpers import API
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Category, Passport, Product
from app.modules.catalogue import service


async def _unscreened(db, n: int) -> list[str]:
    """n products nobody has screened: the first has a tier-1 passport, the rest none at all."""
    category = (await db.execute(select(Category.id).limit(1))).scalar_one()
    rows = [Product(category_id=category, canonical_name=f"Qzscreen Widget {i}",
                    model_number=f"QZS-{i}", model_number_normalized=f"QZS{i}",
                    public_slug=f"t-{uuid.uuid4().hex[:12]}", identification_source="manual")
            for i in range(n)]
    db.add_all(rows)
    await db.flush()
    db.add(Passport(product_id=rows[0].id, version=1, tier=1, status_badge="needs_information",
                    formula_version="test"))
    await db.flush()
    return [str(p.id) for p in rows]


async def _ids(db, q: str, limit: int, offset: int = 0, screened: bool = False) -> list[str]:
    return [r["id"] for r in await service.search(db, q, limit, None, offset, screened)]


async def test_screened_leaves_out_products_without_a_tier_2_passport():
    async with SessionLocal() as db:
        new = await _unscreened(db, 4)
        # Default unchanged: the newest products, screened or not.
        assert set(new) <= set(await _ids(db, "", 10))
        assert set(new) <= set(await _ids(db, "qzscreen", 10))
        assert await _ids(db, "QZS-2", 10) == [new[2]]
        # Screened: none of them, by any route (newest, words, an exact model number).
        listed = await service.search(db, "", 50, None, 0, True)
        assert listed and all(p["tier"] == 2 for p in listed)
        assert not set(new) & {p["id"] for p in listed}
        assert not set(new) & set(await _ids(db, "qzscreen", 10, screened=True))
        assert await _ids(db, "QZS-2", 10, screened=True) == []
        await db.rollback()


async def test_screened_pages_continue_each_other():
    async with SessionLocal() as db:
        await _unscreened(db, 12)  # newer than every screened product: must not thin the pages
        whole = await _ids(db, "", 50, screened=True)
        pages = [i for o in range(0, len(whole), 2) for i in await _ids(db, "", 2, o, screened=True)]
        assert len(whole) >= 3 and pages == whole
        await db.rollback()


async def test_the_route_takes_screened_and_needs_no_account(client):
    r = await client.get(f"{API}/products", params={"screened": "true", "limit": 3})
    assert r.status_code == 200 and r.headers["X-Has-More"] in {"true", "false"}
    assert r.json() and all(p["tier"] == 2 for p in r.json())
    default = (await client.get(f"{API}/products", params={"limit": 3})).json()
    explicit = (await client.get(f"{API}/products", params={"limit": 3, "screened": "false"})).json()
    assert [p["id"] for p in explicit] == [p["id"] for p in default]
