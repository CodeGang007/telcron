"""WO-017 QA: `POST /auth/resend` (WO-013, DEF-004) really issues a new, working code once the
minute has passed, and the earlier code stops working. Before this test only the refusal inside
the minute was asserted, so a resend that never sent anything still passed."""

from datetime import timedelta

from helpers import API, signup

from app.modules.identity import service


async def test_after_a_minute_resend_issues_a_new_code_that_verifies(client, monkeypatch):
    email, first = await signup(client)
    monkeypatch.setattr(service, "RESEND_GAP", timedelta(0))  # the minute has passed
    r = await client.post(f"{API}/auth/resend", json={"email": email})
    assert r.status_code == 202
    new = r.json()["dev_codes"]
    assert new and new["email"]
    if new["email"] != first["email"]:
        old = await client.post(f"{API}/auth/verify",
                                json={"email": email, "channel": "email", "code": first["email"]})
        assert old.status_code == 400  # a new code replaces the earlier unused one
    ok = await client.post(f"{API}/auth/verify",
                           json={"email": email, "channel": "email", "code": new["email"]})
    assert ok.status_code == 200 and ok.json()["verification_level"] == 1


async def test_a_verified_address_gets_no_new_code(client, monkeypatch):
    email, codes = await signup(client)
    await client.post(f"{API}/auth/verify",
                      json={"email": email, "channel": "email", "code": codes["email"]})
    monkeypatch.setattr(service, "RESEND_GAP", timedelta(0))
    r = await client.post(f"{API}/auth/resend", json={"email": email})
    assert r.status_code == 202 and r.json() == {"sent": True, "dev_codes": None}
