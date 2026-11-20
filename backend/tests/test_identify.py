"""Scanning a barcode: the registry first, then the public product database, then a passport."""

import pytest
from helpers import API, verified_user
from sqlalchemy import select

from app.models import IdentificationRequest
from app.modules.catalogue import identify, upcitemdb

KETTLE = {"title": "Brewmaster 1.7L Electric Kettle", "brand": "Brewmaster", "model": "BM-17",
          "category": "Home & Garden > Kitchen & Dining > Kitchen Appliances > Electric Kettles",
          "description": "Stainless steel kettle with auto shut-off."}


def test_barcodes_are_checked_and_stored_as_14_digits():
    assert identify.gtin14("885909950805") == "00885909950805"  # UPC-A
    assert identify.gtin14("4006381333931") == "04006381333931"  # EAN-13
    assert identify.gtin14("885909950806") is None  # wrong check digit
    assert identify.gtin14("12345") is None


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
    assert passport["version"] == 1 and passport["tier"] == 2
    # Scanned again: answered by the registry, no second product, no second lookup.
    again = (await client.post(f"{API}/identify", json={"barcode": "036000291452"})).json()
    assert (again["slug"], again["new"], len(calls)) == (body["slug"], False, 1)
    rows = (await db.execute(select(IdentificationRequest).where(
        IdentificationRequest.barcode_value == "00036000291452")
        .order_by(IdentificationRequest.created_at))).scalars().all()
    assert [(r.status, r.cache_hit) for r in rows] == [("identified", False), ("identified", True)]


@pytest.mark.parametrize("outcome, status, detail", [
    (None, 404, "product_not_identified"),
    (upcitemdb.LookupUnavailable("HTTP 429"), 503, "lookup_unavailable"),
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
