"""WO-017 QA: access tests the WO-014 routes did not carry (telcron-testing: no token is 401, a
level too low is 403). Before these, only `/identify/photo` without a token was asserted."""

from helpers import API, login, signup

PHOTO = {"images": ["data:image/jpeg;base64,/9j/AAAA"], "barcode": "8907770000006"}


async def _level_zero(client, monkeypatch):
    # Level 0 that can sign in exists only while the phone is required too (ADR-006).
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "level1_requires_phone", True)
    email, codes = await signup(client)
    r = await client.post(f"{API}/auth/verify",
                          json={"email": email, "channel": "email", "code": codes["email"]})
    assert r.status_code == 200 and r.json()["verification_level"] == 0
    _, headers = await login(client, email)
    return headers


async def test_asking_for_research_without_signing_in_is_401(client):
    r = await client.post(f"{API}/products/aquablend-900/research")
    assert r.status_code == 401


async def test_asking_for_research_below_level_1_is_403(client, monkeypatch):
    headers = await _level_zero(client, monkeypatch)
    r = await client.post(f"{API}/products/aquablend-900/research", headers=headers)
    assert r.status_code == 403


async def test_identifying_from_a_photo_below_level_1_is_403(client, monkeypatch):
    headers = await _level_zero(client, monkeypatch)
    r = await client.post(f"{API}/identify/photo", headers=headers, json=PHOTO)
    assert r.status_code == 403


async def test_the_research_summary_needs_no_account(client):
    assert (await client.get(f"{API}/products/aquablend-900/research")).status_code == 200
