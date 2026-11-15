"""End to end against the real database: sign-up to coins, review to re-screen to alert."""

import uuid

from sqlalchemy import select

from app.models import CoinLedgerEntry, HazardFlag, OutboxEvent, Passport, Product, User
from app.modules.rewards.service import confirm_entry
from app.modules.screening.service import screen_product

API = "/api/v1"
PASSWORD = "correct-horse-battery"


async def signup(client, name="Tester"):
    email = f"{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(f"{API}/auth/register", json={
        "email": email, "password": PASSWORD, "display_name": name, "phone_e164": "+15550001111"})
    assert r.status_code == 201, r.text
    return email, r.json()["dev_codes"]


async def verified_user(client, name="Tester"):
    email, codes = await signup(client, name)
    for channel in ("email", "phone"):
        r = await client.post(f"{API}/auth/verify", json={
            "email": email, "channel": channel, "code": codes[channel]})
        assert r.status_code == 200, r.text
    assert r.json()["verification_level"] == 1
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    tokens = r.json()
    return email, tokens, {"Authorization": f"Bearer {tokens['access_token']}"}


async def confirm_pending(db, user_id):
    ids = (await db.execute(select(CoinLedgerEntry.id).where(
        CoinLedgerEntry.user_id == user_id, CoinLedgerEntry.status == "pending"))).scalars().all()
    for entry_id in ids:
        await confirm_entry(db, entry_id)
    await db.commit()


async def test_search_and_passport_need_no_account(client):
    r = await client.get(f"{API}/products", params={"q": "aquablend"})
    assert r.status_code == 200 and r.json()[0]["slug"] == "aquablend-900"
    r = await client.post(f"{API}/identify", json={"barcode": "0850012345678"})
    assert r.json()["slug"] == "aquablend-900"
    assert (await client.get(f"{API}/products/nope")).status_code == 404


async def test_level_zero_cannot_contribute(client):
    email, _ = await signup(client)
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (await client.get(f"{API}/wallet/items", headers=headers)).status_code == 403
    assert (await client.get(f"{API}/wallet/items")).status_code == 401


async def test_wrong_code_is_refused_and_counted(client):
    email, codes = await signup(client)
    wrong = "000000" if codes["email"] != "000000" else "111111"
    for _ in range(5):
        r = await client.post(f"{API}/auth/verify",
                              json={"email": email, "channel": "email", "code": wrong})
        assert r.status_code == 400
    # Five misses burn the code: even the right one is refused now.
    r = await client.post(f"{API}/auth/verify",
                          json={"email": email, "channel": "email", "code": codes["email"]})
    assert r.status_code == 400


async def test_signup_to_coins(client, db):
    _, _, headers = await verified_user(client)
    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    assert me["verification_level"] == 1 and me["trust_score"] == 10.0
    coins = (await client.get(f"{API}/coins", headers=headers)).json()
    assert coins["pending"] == 100 and coins["confirmed"] == 0

    await confirm_pending(db, uuid.UUID(me["id"]))
    coins = (await client.get(f"{API}/coins", headers=headers)).json()
    assert coins == {"confirmed": 100, "pending": 0, "frozen": 0, "lifetime_earned": 100,
                     "level": {"level": 1, "title": "Novice", "next_title": "Contributor",
                               "next_at": 250}}


async def test_refresh_rotates_and_reuse_kills_the_family(client):
    _, tokens, _ = await verified_user(client)
    r1 = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    new = r1.json()
    # The old access token died with its session row.
    old = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.get(f"{API}/auth/me", headers=old)).status_code == 401
    # Replaying the used refresh token revokes everything, including the new session.
    r2 = await client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401
    fresh = {"Authorization": f"Bearer {new['access_token']}"}
    assert (await client.get(f"{API}/auth/me", headers=fresh)).status_code == 401
    r3 = await client.post(f"{API}/auth/refresh", json={"refresh_token": new["refresh_token"]})
    assert r3.status_code == 401


async def test_lockout_after_five_bad_passwords(client):
    email, _ = await signup(client)
    for _ in range(5):
        r = await client.post(f"{API}/auth/login", json={"email": email, "password": "wrong-pass"})
        assert r.status_code == 401
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 423


async def test_review_rescreens_and_alerts_the_wallet_holder(client, db):
    slug = "voltpro-65w-charger"
    product = (await db.execute(select(Product).where(Product.public_slug == slug))).scalar_one()
    await screen_product(db, product.id, "ingest")
    await db.commit()
    before = (await client.get(f"{API}/products/{slug}/passport")).json()

    _, _, holder = await verified_user(client, "Holder")
    r = await client.post(f"{API}/wallet/items", headers=holder, json={"product_id": slug})
    assert r.status_code == 201
    r = await client.post(f"{API}/wallet/items", headers=holder, json={"product_id": slug})
    assert r.status_code == 409

    _, _, reviewer = await verified_user(client, "Reviewer")
    body = ("It started to overheat, then smoke came out and it caused a burn on my hand. "
            "There was a small fire and an electric shock.")
    r = await client.post(f"{API}/products/{slug}/reviews", headers=reviewer,
                          json={"rating": 1, "title": "Dangerous", "body": body})
    assert r.status_code == 201 and r.json()["coins_pending"] == 40  # review 10 + first 30
    r = await client.post(f"{API}/products/{slug}/reviews", headers=reviewer,
                          json={"rating": 1, "body": body})
    assert r.status_code == 409

    # A flag the safety team has confirmed (confirmation has no endpoint yet: WO-006).
    reviewer_id = (await client.get(f"{API}/auth/me", headers=reviewer)).json()["id"]
    assert await db.get(User, uuid.UUID(reviewer_id)) is not None
    db.add(HazardFlag(reporter_user_id=uuid.UUID(reviewer_id), product_id=product.id,
                      status="confirmed",
                      description="Banned counterfeit unit: fire and burn injury, defective, "
                                  "cracked casing, and the cable coating is toxic to pets."))
    await db.commit()

    # The review wrote its event in the same transaction; the screening handler does this.
    event = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "ReviewSubmitted").order_by(OutboxEvent.created_at.desc())
        .limit(1))).scalar_one()
    assert event.payload["product_id"] == str(product.id)
    from app.workers.handlers import alerts, screening
    await screening.handle("ReviewSubmitted", event.payload)

    after = (await client.get(f"{API}/products/{slug}/passport")).json()
    assert after["version"] == before["version"] + 1
    assert [h["version"] for h in after["history"]][:2] == [after["version"], before["version"]]
    health = next(d for d in after["hazard"]["dimensions"] if d["code"] == "health_safety")
    assert health["status"] == "scored" and health["score"] > 0
    assert any("overheat" in c["excerpt"] for c in health["citations"])
    # The old passport row is untouched: append-only.
    old = (await db.execute(select(Passport).where(
        Passport.id == uuid.UUID(before["passport_id"])))).scalar_one()
    assert float(old.trust_score) == before["trust_score"]

    assert before["status_badge"] == "verified" and after["status_badge"] == "caution"
    assert after["hazard"]["label"] == "medium"
    issued = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "PassportIssued",
        OutboxEvent.payload["product_id"].astext == str(product.id))
        .order_by(OutboxEvent.created_at.desc()).limit(1))).scalar_one()
    await alerts.handle("PassportIssued", issued.payload)
    got = (await client.get(f"{API}/alerts", headers=holder)).json()
    assert len(got) == 1 and got[0]["product_slug"] == slug
    assert (await client.get(f"{API}/alerts", headers=reviewer)).json() == []


async def test_wallet_item_of_another_user_is_a_404(client):
    _, _, a = await verified_user(client, "Ana")
    _, _, b = await verified_user(client, "Ben")
    item = (await client.post(f"{API}/wallet/items", headers=a,
                              json={"product_id": "aquablend-900"})).json()
    assert (await client.delete(f"{API}/wallet/items/{item['id']}", headers=b)).status_code == 404
    assert (await client.delete(f"{API}/wallet/items/{item['id']}", headers=a)).status_code == 204
    assert (await client.get(f"{API}/wallet/items", headers=a)).json() == []


async def test_staff_routes_refuse_ordinary_users(client):
    _, _, headers = await verified_user(client)
    assert (await client.get(f"{API}/review-tasks", headers=headers)).status_code == 403
    r = await client.post(f"{API}/screenings", headers=headers,
                          json={"product_id": str(uuid.uuid4())})
    assert r.status_code == 403


async def test_recalled_product_reads_recalled_with_the_recall_cited(client, db):
    slug = "brightbuild-magnet-set"
    product = (await db.execute(select(Product).where(Product.public_slug == slug))).scalar_one()
    await screen_product(db, product.id, "ingest")
    await db.commit()
    from app.core.redis import get_redis
    await (await get_redis()).delete(f"telcron:passport:{product.id}")
    view = (await client.get(f"{API}/products/{slug}/passport")).json()
    assert view["status_badge"] == "recalled"
    assert view["recall_matches"][0]["verdict"] == "match"
    regulatory = next(d for d in view["hazard"]["dimensions"] if d["code"] == "regulatory_flags")
    assert regulatory["citations"] and regulatory["citations"][0]["kind"] == "recall"
