"""WO-017 QA: WO-014's matching rule "two different model numbers never match". Before this test
only the positive case (one product under two barcodes) was asserted."""

import uuid

from helpers import API
from test_research import fresh_upc

from app.modules.catalogue import upcitemdb


async def test_two_model_numbers_of_one_brand_are_two_products(client, monkeypatch):
    first, second = fresh_upc(), fresh_upc()
    brand = f"Zephyr{uuid.uuid4().hex[:6]}"

    async def listing(gtin):
        model = "TF-90" if gtin.endswith(first) else "TF-120"
        # Identical titles: only the model numbers tell them apart.
        return {"title": f"{brand} Tower Fan Oscillating", "brand": brand, "model": model,
                "category": "Fans"}
    monkeypatch.setattr(upcitemdb, "lookup", listing)
    a = (await client.post(f"{API}/identify", json={"barcode": first})).json()
    b = (await client.post(f"{API}/identify", json={"barcode": second})).json()
    assert a["new"] is True and b["new"] is True
    assert a["slug"] != b["slug"]
