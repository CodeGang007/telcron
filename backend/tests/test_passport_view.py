"""The passport read (CT-003 §A, DEF-113): "no recall found" is true as of the recall corpus the
screening read, and the passport says which date that is."""

import uuid
from datetime import datetime

from helpers import API, product_id
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.redis import get_redis
from app.models import Category, Passport, Product, Screening
from app.modules.catalogue import service


async def _uncached(product: uuid.UUID) -> None:
    await (await get_redis()).delete(f"telcron:passport:{product}")


async def test_the_passport_states_the_corpus_date_of_its_screening(client, db):
    pid = await product_id(db, "voltpro-65w-charger")
    await _uncached(pid)
    view = (await client.get(f"{API}/products/voltpro-65w-charger/passport")).json()
    synced = (await db.execute(select(Screening.corpus_synced_at)
                               .join(Passport, Passport.screening_id == Screening.id)
                               .where(Passport.id == uuid.UUID(view["passport_id"])))).scalar_one()
    assert view["recall_checked_as_of"] == synced.isoformat()
    assert datetime.fromisoformat(view["recall_checked_as_of"]).tzinfo is not None
    # The cached copy says the same.
    again = (await client.get(f"{API}/products/voltpro-65w-charger/passport")).json()
    assert again["recall_checked_as_of"] == view["recall_checked_as_of"]


async def test_a_passport_without_a_screening_has_no_as_of_date():
    async with SessionLocal() as db:
        category = (await db.execute(select(Category.id).limit(1))).scalar_one()
        product = Product(category_id=category, canonical_name="Unscreened Thing",
                          public_slug=f"t-{uuid.uuid4().hex[:12]}", identification_source="manual")
        db.add(product)
        await db.flush()
        db.add(Passport(product_id=product.id, version=1, tier=1,
                        status_badge="needs_information", formula_version="test"))
        await db.flush()
        await db.refresh(product)
        try:
            view = await service.passport_view(db, product)
            assert view is not None and view["recall_checked_as_of"] is None
        finally:
            await _uncached(product.id)
            await db.rollback()
