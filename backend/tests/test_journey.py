"""End to end against the designed database: sign-up to coins, review to re-screen,
recall to alert."""

import uuid

import pytest
from demo_catalogue import add_recall
from helpers import API, PASSWORD, login, new_phone, product_id, signup, verified_user
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.models import CoinBalance, OutboxEvent, Passport
from app.modules.rewards import service as rewards
from app.workers.handlers import alerts, screening


async def test_search_and_passport_need_no_account(client):
    r = await client.get(f"{API}/products", params={"q": "aquablend"})
    assert r.status_code == 200 and r.json()[0]["slug"] == "aquablend-900"
    r = await client.post(f"{API}/identify", json={"barcode": "00850012345678"})
    assert r.json()["slug"] == "aquablend-900"
    r = await client.get(f"{API}/products/voltpro-65w-charger/passport")
    assert r.status_code == 200 and r.json()["status_badge"] == "verified"
    assert (await client.get(f"{API}/products/nope")).status_code == 404


async def test_level_zero_can_sign_in_but_not_contribute(client):
    email, _ = await signup(client)
    _, headers = await login(client, email)
    assert (await client.get(f"{API}/auth/me", headers=headers)).json()["verification_level"] == 0
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


async def test_email_alone_reaches_level_1(client):
    email, codes = await signup(client)
    assert set(codes) == {"email"}  # no phone code while there is no SMS route (ADR-006)
    r = await client.post(f"{API}/auth/verify", json={
        "email": email, "channel": "email", "code": codes["email"]})
    assert r.json()["verification_level"] == 1


async def test_a_new_code_can_be_requested_once_a_minute(client):
    email, first = await signup(client)
    assert (await client.post(f"{API}/auth/resend", json={"email": email})).json()["dev_codes"] is None
    # Unknown addresses get the same answer: the endpoint does not reveal who has an account.
    unknown = await client.post(f"{API}/auth/resend", json={"email": "nobody@example.com"})
    assert unknown.status_code == 202 and unknown.json()["sent"] is True


async def test_a_phone_number_has_one_verified_owner(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "level1_requires_phone", True)
    phone = new_phone()
    first, codes = await signup(client, "First", phone)
    for channel in ("email", "phone"):
        await client.post(f"{API}/auth/verify", json={
            "email": first, "channel": channel, "code": codes[channel]})
    second, codes = await signup(client, "Second", phone)
    r = await client.post(f"{API}/auth/verify", json={
        "email": second, "channel": "phone", "code": codes["phone"]})
    assert r.status_code == 409 and r.json()["detail"] == "phone_in_use"


async def test_signup_to_coins(client, db):
    _, _, headers = await verified_user(client)
    me = (await client.get(f"{API}/auth/me", headers=headers)).json()
    assert me["verification_level"] == 1 and me["trust_score"] == 10.0
    coins = (await client.get(f"{API}/coins", headers=headers)).json()
    assert coins["pending"] == 105 and coins["confirmed"] == 0

    await rewards.confirm_due(db)  # what the coins handler does
    await db.commit()
    coins = (await client.get(f"{API}/coins", headers=headers)).json()
    assert coins == {"confirmed": 105, "pending": 0, "frozen": 0, "lifetime_earned": 105,
                     "level": {"level": 1, "title": "Novice", "next_title": "Inspector",
                               "next_at": 200}}


async def test_a_repeated_earn_awards_once(client, db):
    _, _, headers = await verified_user(client)
    user_id = uuid.UUID((await client.get(f"{API}/auth/me", headers=headers)).json()["id"])
    subject = await product_id(db, "aquablend-900")
    key = f"photo:{uuid.uuid4()}"
    first = await rewards.earn(db, user_id, "photo", subject_type="product", subject_id=subject,
                               idempotency_key=key)
    again = await rewards.earn(db, user_id, "photo", subject_type="product", subject_id=subject,
                               idempotency_key=key)
    await db.commit()
    assert first is not None and int(first.amount) == 15 and again is None
    balance = await db.get(CoinBalance, user_id)
    assert int(balance.pending_balance) == 100 + 5 + 15  # Level 1, the first daily sign-in, one photo


async def test_the_ledger_cannot_be_edited_directly(db):
    entry = (await db.execute(text("select id from coin_ledger_entries limit 1"))).scalar_one()
    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(text("update coin_ledger_entries set amount = 999999 where id = :id"),
                         {"id": entry})
    await db.rollback()


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


async def test_a_review_rescreens_and_the_new_score_cites_it(client, db):
    slug = "voltpro-65w-charger"
    before = (await client.get(f"{API}/products/{slug}/passport")).json()

    _, _, reviewer = await verified_user(client, "Reviewer")
    body = ("It started to overheat, then smoke came out and it caused a burn on my hand. "
            "There was a small fire and an electric shock.")
    r = await client.post(f"{API}/products/{slug}/reviews", headers=reviewer,
                          json={"rating": 1, "title": "Dangerous", "body": body})
    assert r.status_code == 201 and r.json()["coins_pending"] == 40  # review 10 + first 30
    r = await client.post(f"{API}/products/{slug}/reviews", headers=reviewer,
                          json={"rating": 1, "body": body})
    assert r.status_code == 409

    # The review wrote its event in the same transaction; the screening handler does this.
    event = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "ReviewSubmitted").order_by(OutboxEvent.created_at.desc())
        .limit(1))).scalar_one()
    assert event.payload["product_id"] == before["product_id"]
    await screening.handle("ReviewSubmitted", event.payload)

    after = (await client.get(f"{API}/products/{slug}/passport")).json()
    assert after["version"] == before["version"] + 1
    assert [h["version"] for h in after["history"]][:2] == [after["version"], before["version"]]
    # A hazard finding lowers the trust score; it does not change the badge.
    assert after["status_badge"] == "verified" and after["trust_score"] < before["trust_score"]
    assert after["hazard"]["label"] in ("Low", "Medium", "High")
    health = next(d for d in after["hazard"]["dimensions"] if d["code"] == "safety.health_safety")
    assert health["status"] == "scored" and health["score"] > 0
    assert any("overheat" in c["excerpt"] for c in health["citations"])
    # The earlier version still exists, unchanged: passports are insert-only.
    old = await db.get(Passport, uuid.UUID(before["passport_id"]))
    assert float(old.trust_score) == before["trust_score"]


async def test_a_recall_reaches_the_wallet_holder_once(client, db):
    slug = "aquablend-900"
    _, _, holder = await verified_user(client, "Holder")
    r = await client.post(f"{API}/wallet/items", headers=holder, json={"product_id": slug})
    assert r.status_code == 201 and r.json()["status"] == "active"
    r = await client.post(f"{API}/wallet/items", headers=holder, json={"product_id": slug})
    assert r.status_code == 409
    _, _, bystander = await verified_user(client, "Bystander")

    await add_recall(db, external_id="TEST-26-002", product_name="AquaBlend 900 Blender",
                     brand="AquaBlend", model="AB-900",
                     title="AquaBlend 900 blenders recalled: blade can detach",
                     hazard="Laceration hazard")
    await db.commit()
    pid = await product_id(db, slug)
    await screening.handle("RecallImported", {"product_id": str(pid)})

    view = (await client.get(f"{API}/products/{slug}/passport")).json()
    assert view["status_badge"] == "recalled" and view["recall_matches"][0]["verdict"] == "match"

    raised = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "RiskEventRaised",
        OutboxEvent.payload["product_id"].astext == str(pid)))).scalars().all()
    assert len(raised) == 1
    await alerts.handle("RiskEventRaised", raised[0].payload)
    await alerts.handle("RiskEventRaised", raised[0].payload)  # delivered twice, alerted once
    got = (await client.get(f"{API}/alerts", headers=holder)).json()
    assert len(got) == 1
    assert (got[0]["event_type"], got[0]["severity"], got[0]["product_slug"]) == (
        "recall_match", "critical", slug)
    assert (await client.get(f"{API}/alerts", headers=bystander)).json() == []

    # A second screening finds nothing new: no second event, no second alert.
    await screening.handle("RecallImported", {"product_id": str(pid)})
    again = (await db.execute(select(OutboxEvent).where(
        OutboxEvent.event_type == "RiskEventRaised",
        OutboxEvent.payload["product_id"].astext == str(pid)))).scalars().all()
    assert len(again) == 1


async def test_wallet_item_of_another_user_is_a_404(client):
    slug = "voltpro-65w-charger"
    _, _, a = await verified_user(client, "Ana")
    _, _, b = await verified_user(client, "Ben")
    item = (await client.post(f"{API}/wallet/items", headers=a, json={"product_id": slug})).json()
    assert (await client.delete(f"{API}/wallet/items/{item['id']}", headers=b)).status_code == 404
    assert (await client.delete(f"{API}/wallet/items/{item['id']}", headers=a)).status_code == 204
    assert (await client.get(f"{API}/wallet/items", headers=a)).json() == []


async def test_staff_routes_refuse_ordinary_users(client):
    _, _, headers = await verified_user(client)
    assert (await client.get(f"{API}/review-tasks", headers=headers)).status_code == 403
    r = await client.post(f"{API}/screenings", headers=headers,
                          json={"product_id": str(uuid.uuid4())})
    assert r.status_code == 403


async def test_recalled_product_reads_recalled_with_the_recall_cited(client):
    view = (await client.get(f"{API}/products/brightbuild-magnet-set/passport")).json()
    assert view["status_badge"] == "recalled" and view["tier"] == 2
    assert view["recall_matches"][0]["verdict"] == "match"
    regulatory = next(d for d in view["hazard"]["dimensions"] if d["code"] == "safety.regulatory")
    assert regulatory["citations"] and regulatory["citations"][0]["kind"] == "recall"


async def test_rewards_overview_and_the_store(client, db):
    _, _, member = await verified_user(client)
    overview = (await client.get(f"{API}/rewards", headers=member)).json()
    assert overview["streak_days"] == 1 and overview["level"] == 1
    assert [x["title"] for x in overview["levels"]][:2] == ["Novice", "Inspector"]
    assert {"review", "login_streak"} <= {w["code"] for w in overview["ways_to_earn"]}
    report = next(i for i in overview["store"] if i["code"] == "hazard_report_pdf")
    assert report["cost"] == 50 and report["needs_product"]
    # Pending coins cannot be spent.
    r = await client.post(f"{API}/redemptions", headers=member, json={
        "item_code": "hazard_report_pdf", "product": "aquablend-900", "request_id": "a"})
    assert r.status_code == 409 and r.json()["detail"] == "not_enough_coins"
    await rewards.confirm_due(db)
    await db.commit()
    r = await client.post(f"{API}/redemptions", headers=member, json={
        "item_code": "hazard_report_pdf", "product": "aquablend-900", "request_id": "b"})
    assert r.status_code == 201 and r.json()["status"] == "fulfilled"
    again = await client.post(f"{API}/redemptions", headers=member, json={
        "item_code": "hazard_report_pdf", "product": "aquablend-900", "request_id": "b"})
    assert again.json()["id"] == r.json()["id"]  # a retried click spends once
    assert (await client.get(f"{API}/coins", headers=member)).json()["confirmed"] == 105 - 50


async def test_lists_are_paged(client):
    first = await client.get(f"{API}/products", params={"limit": 2})
    second = await client.get(f"{API}/products", params={"limit": 2, "offset": 2})
    assert first.headers["X-Has-More"] == "true" and len(first.json()) == 2
    assert not {p["id"] for p in first.json()} & {p["id"] for p in second.json()}
    last = await client.get(f"{API}/products", params={"limit": 50})
    assert last.headers["X-Has-More"] == "false"


async def test_the_code_is_emailed_and_a_refused_send_does_not_break_sign_up(client, monkeypatch):
    from app.core.config import get_settings
    from app.modules.identity import mailer
    s = get_settings()
    monkeypatch.setattr(s, "mail_provider", "ses")
    monkeypatch.setattr(s, "mail_from", "Telcron <codes@example.com>")
    sent = []
    monkeypatch.setattr(mailer, "_send_ses", lambda to, code: sent.append((to, code)))
    email, codes = await signup(client)
    assert sent == [(email, codes["email"])]
    assert mailer._body(codes["email"], 10)[0] == f"{codes['email']} is your Telcron code"

    def refuse(to, code):
        raise RuntimeError("Email address is not verified (SES sandbox)")
    monkeypatch.setattr(mailer, "_send_ses", refuse)
    email, codes = await signup(client)  # still 201: the member can ask for a new code
    assert codes["email"]
