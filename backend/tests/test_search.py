"""Text search (DEF-080): read through the trigram index, a bounded window per list, and still the
same answers: typos, a brand, a fragment of a word, and pages that continue one another."""

import uuid

from helpers import API
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Brand, Category, Product
from app.modules.catalogue import service


async def _catalogue(db, names: list[str], brand: Brand | None = None) -> list[str]:
    category = (await db.execute(select(Category.id).limit(1))).scalar_one()
    rows = [Product(category_id=category, brand_id=brand.id if brand else None, canonical_name=n,
                    public_slug=f"t-{uuid.uuid4().hex[:12]}", identification_source="manual")
            for n in names]
    db.add_all(rows)
    await db.flush()
    return [str(p.id) for p in rows]


async def _ids(db, q: str, limit: int, offset: int = 0) -> list[str]:
    return [r["id"] for r in await service.search(db, q, limit, None, offset)]


async def test_a_typo_still_finds_the_product(client):
    found = (await client.get(f"{API}/products", params={"q": "blendr"})).json()
    assert "aquablend-900" in [p["slug"] for p in found]


async def test_pages_continue_each_other_through_ties():
    async with SessionLocal() as db:
        await _catalogue(db, [f"Tiedname Kettle {i}" for i in range(80)])
        whole = await _ids(db, "tiedname kettle", 60)
        pages = [i for o in range(0, 60, 10) for i in await _ids(db, "tiedname kettle", 10, o)]
        assert len(whole) == 60 and pages == whole
        await db.rollback()


async def test_a_fragment_inside_a_word_is_found_beyond_closer_names():
    # "len" is only a quarter like "Blender" by word similarity, as like as "Lamp"; "Le Nord" is
    # closer. Every name containing the text is still listed, ahead of names that do not.
    async with SessionLocal() as db:
        await _catalogue(db, [f"Le Nord Fan {i}" for i in range(60)])
        lamps = await _catalogue(db, [f"Lamp Shade {i}" for i in range(200)])
        blenders = await _catalogue(db, [f"Qblender Unit {i}" for i in range(20)])
        found = await _ids(db, "len", 100)
        assert set(blenders) <= set(found) and not set(lamps) & set(found)
        await db.rollback()


async def test_a_brand_finds_products_whose_names_do_not_carry_it_page_after_page():
    async with SessionLocal() as db:
        brand = Brand(name="Zorvex", normalized_name="zorvex")
        db.add(brand)
        await db.flush()
        await _catalogue(db, [f"Zorvan Filler {i}" for i in range(100)])  # closer by name alone
        kettles = await _catalogue(db, [f"Cordless Kettle {i}" for i in range(30)], brand)
        whole = await _ids(db, "zorvex", 40)
        pages = [i for o in range(0, 40, 10) for i in await _ids(db, "zorvex", 10, o)]
        assert set(whole[:30]) == set(kettles) and pages == whole
        await db.rollback()
