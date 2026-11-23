"""Scanning a barcode: the registry first, then the public product database, then a passport."""

import uuid

import pytest
from helpers import API, verified_user
from sqlalchemy import select

from app.models import IdentificationRequest
from app.modules.catalogue import identify, openfacts, upcitemdb, vision

KETTLE = {"title": "Brewmaster 1.7L Electric Kettle", "brand": "Brewmaster", "model": "BM-17",
          "category": "Home & Garden > Kitchen & Dining > Kitchen Appliances > Electric Kettles",
          "description": "Stainless steel kettle with auto shut-off."}


def test_barcodes_are_checked_and_stored_as_14_digits():
    assert identify.gtin14("885909950805") == "00885909950805"  # UPC-A
    assert identify.gtin14("4006381333931") == "04006381333931"  # EAN-13
    assert identify.gtin14("885909950806") is None  # wrong check digit
    assert identify.gtin14("12345") is None
    # UPC-E, the short code on small packages: its check digit belongs to the expanded UPC-A.
    assert identify.upce_to_upca("04252614") == "042100005264"
    assert identify.gtin14("04252614") == "00042100005264"
    assert identify.gtin14("0 42526 1 4") == "00042100005264"  # as printed, with spaces


async def test_a_barcode_typed_with_spaces_is_accepted(client):
    r = await client.post(f"{API}/identify", json={"barcode": "8 50012 34567 8"})
    assert r.status_code == 200 and r.json()["slug"] == "aquablend-900"


def test_categories_are_mapped():
    assert identify.category_code("Electronics > Phones > Mobile Phones") == "smartphones"
    assert identify.category_code(KETTLE["category"]) == "appliances"
    assert identify.category_code(None) == "household"


async def test_a_known_barcode_is_answered_from_the_registry(client, monkeypatch):
    async def must_not_call(gtin):
        raise AssertionError("the registry already knows this barcode")
    monkeypatch.setattr(upcitemdb, "lookup", must_not_call)
    r = await client.post(f"{API}/identify", json={"barcode": "850012345678"})  # AquaBlend, 12 digits
    assert r.status_code == 200 and r.json() == {
        "slug": "aquablend-900", "name": "AquaBlend 900 Blender", "new": False}


async def test_an_unknown_barcode_is_looked_up_added_and_screened(client, db, monkeypatch):
    calls = []

    async def fake(gtin):
        calls.append(gtin)
        return KETTLE
    monkeypatch.setattr(upcitemdb, "lookup", fake)
    r = await client.post(f"{API}/identify", json={"barcode": "036000291452"})
    body = r.json()
    assert r.status_code == 200 and body["new"] is True and body["name"] == KETTLE["title"]
    passport = (await client.get(f"{API}/products/{body['slug']}/passport")).json()
    # Identified, but nothing is checked yet: no badge or score until there is evidence.
    assert (passport["version"], passport["tier"], passport["status_badge"]) == (1, 1, "needs_information")
    # Scanned again: answered by the registry, no second product, no second lookup.
    again = (await client.post(f"{API}/identify", json={"barcode": "036000291452"})).json()
    assert (again["slug"], again["new"], len(calls)) == (body["slug"], False, 1)
    rows = (await db.execute(select(IdentificationRequest).where(
        IdentificationRequest.barcode_value == "00036000291452")
        .order_by(IdentificationRequest.created_at))).scalars().all()
    assert [(r.status, r.cache_hit) for r in rows] == [("identified", False), ("identified", True)]


@pytest.mark.parametrize("outcome, status, detail", [
    (None, 404, "product_not_identified"),
    # UPCitemdb's daily limit alone is not a failure: the open databases are asked next.
    (upcitemdb.LookupUnavailable("HTTP 429"), 404, "product_not_identified"),
])
async def test_what_cannot_be_identified_says_why(client, monkeypatch, outcome, status, detail):
    async def fake(gtin):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(upcitemdb, "lookup", fake)
    r = await client.post(f"{API}/identify", json={"barcode": "012345678905"})
    assert (r.status_code, r.json()["detail"]) == (status, detail)


async def test_a_bad_barcode_and_the_daily_quota(client, db, monkeypatch):
    assert (await client.post(f"{API}/identify", json={"barcode": "885909950806"})).status_code == 422
    async def unknown(gtin):
        return None
    monkeypatch.setattr(upcitemdb, "lookup", unknown)
    _, _, member = await verified_user(client)
    codes = [r.status_code for r in [await client.post(
        f"{API}/identify", headers=member, json={"barcode": "012345678905"}) for _ in range(21)]]
    assert codes[:20] == [404] * 20 and codes[20] == 429


async def test_a_barcode_unknown_in_the_us_is_found_in_the_open_databases(client, monkeypatch):
    async def not_in_us(gtin):
        return None

    async def openfacts_knows(gtin):
        return {"title": "Masala Chai Tea 250 g", "brand": "Chaiwala", "model": None,
                "category": "Food Beverages, Teas", "source": "openfacts"}
    monkeypatch.setattr(upcitemdb, "lookup", not_in_us)
    monkeypatch.setattr(openfacts, "lookup", openfacts_knows)
    r = await client.post(f"{API}/identify", json={"barcode": "8901314077981"})
    assert r.status_code == 200 and r.json()["name"] == "Masala Chai Tea 250 g"


async def test_an_unknown_product_is_identified_from_a_photo_and_confirmed(client, db, monkeypatch):
    async def nobody(gtin):
        return None
    monkeypatch.setattr(upcitemdb, "lookup", nobody)
    monkeypatch.setattr(openfacts, "lookup", nobody)
    seen = {}
    # DEF-122: a brand of this test's own. test_research.py confirms a "Lumina LF-30" desk fan into
    # the shared database, and run after it this product was found, not new.
    brand = f"Breezo{uuid.uuid4().hex[:4]}"

    async def reads(data_urls, hints=None):
        seen["url"], seen["count"] = data_urls[0], len(data_urls)
        return {"brand": brand, "name": f"{brand} Desk Fan 30cm", "model": "LF-30",
                "category": "appliances", "confidence": 0.7}
    monkeypatch.setattr(vision, "read_photo", reads)
    barcode = "8907770000006"
    assert (await client.post(f"{API}/identify", json={"barcode": barcode})).status_code == 404

    photo = {"images": ["data:image/jpeg;base64,/9j/AAAA", "data:image/jpeg;base64,/9j/BBBB"],
             "barcode": barcode}
    assert (await client.post(f"{API}/identify/photo", json=photo)).status_code == 401  # members only
    _, _, member = await verified_user(client)
    suggestion = (await client.post(f"{API}/identify/photo", headers=member, json=photo)).json()
    got = (suggestion["brand"], suggestion["model"], suggestion["category"])
    assert got == (brand, "LF-30", "appliances")
    assert seen["url"].startswith("data:image/jpeg") and seen["count"] == 2  # both sides read
    # A suggestion is not a product: nothing was added yet.
    assert (await client.post(f"{API}/identify", json={"barcode": barcode})).status_code == 404

    # The member corrects the name and confirms.
    r = await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": f"{brand} Desk Fan 30 cm", "brand": brand, "model": "LF-30", "category": "appliances",
        "barcode": barcode, "request_id": suggestion["request_id"]})
    body = r.json()
    assert r.status_code == 200 and body["new"] is True and body["name"] == f"{brand} Desk Fan 30 cm"
    passport = (await client.get(f"{API}/products/{body['slug']}/passport")).json()
    assert passport["version"] == 1
    # The barcode now finds it straight away, and confirming again does not add a second product.
    found = (await client.post(f"{API}/identify", json={"barcode": barcode})).json()
    assert (found["slug"], found["new"]) == (body["slug"], False)
    again = await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": "Another name", "category": "appliances", "barcode": barcode})
    assert (again.json()["slug"], again.json()["new"]) == (found["slug"], False)
    # This test's own request: other tests leave photo requests in the shared database (DEF-122).
    row = (await db.execute(select(IdentificationRequest).where(
        IdentificationRequest.id == uuid.UUID(suggestion["request_id"])))).scalar_one()
    assert row.extracted["from_photo"] is True
    assert row.status == "identified" and row.extracted["model"] == "LF-30"


async def test_a_product_without_a_barcode_can_be_added_by_hand(client):
    _, _, member = await verified_user(client)
    r = await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": "Handmade Wooden Rattle", "category": "household"})
    assert r.status_code == 200 and r.json()["new"] is True
    branded = await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": "Oak Teether", "brand": "Woodly", "category": "household"})
    assert branded.json()["name"] == "Woodly Oak Teether"  # the brand leads, the name is kept
    bad = await client.post(f"{API}/identify/confirm", headers=member, json={
        "name": "Thing", "category": "rockets"})
    assert bad.json()["detail"] == "unknown_category"


async def test_every_database_down_is_a_503(client, monkeypatch):
    async def down(gtin):
        raise upcitemdb.LookupUnavailable("HTTP 429")

    async def also_down(gtin):
        raise openfacts.LookupUnavailable("no answer")
    monkeypatch.setattr(upcitemdb, "lookup", down)
    monkeypatch.setattr(openfacts, "lookup", also_down)
    r = await client.post(f"{API}/identify", json={"barcode": "012345678905"})
    assert (r.status_code, r.json()["detail"]) == (503, "lookup_unavailable")


async def test_the_vision_call_fits_the_providers_limits(monkeypatch):
    """Seen live: the model thought until its budget ran out, and it accepts three images at most."""
    import httpx

    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "llm_api_key", "test")
    sent, calls = {}, []

    async def post(self, url, json=None, headers=None):
        calls.append(1)
        sent.update(json)
        if len(calls) == 1:  # the free plan's per-minute limit, once
            return httpx.Response(429, headers={"retry-after": "0"}, request=httpx.Request("POST", url))
        return httpx.Response(200, request=httpx.Request("POST", url), json={"choices": [{"message": {
            "content": '{"brand": "pilgrim", "name": "Peeling Solution", "confidence": 0.95}'}}]})
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    answer = await vision.read_photo([f"data:image/jpeg;base64,{i}" for i in "ABCD"])
    assert answer["brand"] == "pilgrim" and len(calls) == 2
    images = [p for p in sent["messages"][0]["content"] if p["type"] == "image_url"]
    assert len(images) == 3 and sent["reasoning_effort"] == "none"
