"""QA (DEF-035, CT-002): the gated full report, beyond the owner's tests. The link the redemption
stores opens the report; the refusal is byte-identical whether nobody or another member bought it;
a redemption left `processing` opens nothing; the public reads still need no account."""

import uuid

from helpers import API, verified_user
from sqlalchemy import select

from app.models import Redemption, User
from app.modules.rewards import service as rewards

X, Y = "aquablend-900", "voltpro-65w-charger"


async def member_with_coins(client, db):
    email, _, headers = await verified_user(client)
    await db.commit()
    await rewards.confirm_due(db)
    await db.commit()
    user_id = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
    return user_id, headers


async def test_the_stored_fulfilment_link_opens_the_report(client, db):
    _, headers = await member_with_coins(client, db)
    r = await client.post(f"{API}/redemptions", headers=headers, json={
        "item_code": "hazard_report_pdf", "product": X, "request_id": uuid.uuid4().hex})
    assert r.status_code == 201, r.text
    row = await db.get(Redemption, uuid.UUID(r.json()["id"]))
    link = row.fulfilment["report"]
    pid = (await client.get(f"{API}/products/{X}")).json()["id"]
    assert link == f"/products/{pid}/report"
    opened = await client.get(f"{API}{link}", headers=headers)
    assert opened.status_code == 200 and opened.json()["redemption"]["id"] == r.json()["id"]
    assert opened.headers["cache-control"] == "private, no-store"


async def test_the_refusal_is_byte_identical_whether_nobody_or_another_member_bought_it(client, db):
    _, nobody = await member_with_coins(client, db)
    before = await client.get(f"{API}/products/{Y}/report", headers=nobody)
    _, buyer = await member_with_coins(client, db)
    r = await client.post(f"{API}/redemptions", headers=buyer, json={
        "item_code": "hazard_report_pdf", "product": Y, "request_id": uuid.uuid4().hex})
    assert r.status_code == 201
    after = await client.get(f"{API}/products/{Y}/report", headers=nobody)  # same member, after a purchase
    assert before.status_code == after.status_code == 403
    assert before.content == after.content == b'{"detail":"report_not_redeemed"}'
    assert before.headers.get("content-length") == after.headers.get("content-length")


async def test_a_processing_redemption_opens_nothing(client, db):
    user_id, headers = await member_with_coins(client, db)
    pid = (await client.get(f"{API}/products/{X}")).json()["id"]
    rid = await db.scalar(rewards.REDEEM, {"user": user_id, "item": "hazard_report_pdf",
                                           "key": f"{user_id}:stuck", "product": pid})
    await db.commit()
    assert (await db.get(Redemption, rid)).status == "processing"
    r = await client.get(f"{API}/products/{X}/report", headers=headers)
    assert r.status_code == 403 and r.json() == {"detail": "report_not_redeemed"}


async def test_visitor_and_bad_token_are_401_and_public_reads_stay_open(client):
    r = await client.get(f"{API}/products/{X}/report")
    assert r.status_code == 401 and r.json()["detail"] == "not_authenticated"
    r = await client.get(f"{API}/products/{X}/report", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401
    assert (await client.get(f"{API}/products/{X}")).status_code == 200
    assert (await client.get(f"{API}/products/{X}/passport")).status_code == 200
    # 404 is checked before the entitlement, for a visitor it is still 401 (CurrentUser first).
    r = await client.get(f"{API}/products/no-such-product/report")
    assert r.status_code == 401


async def test_another_item_redeemed_for_the_product_does_not_open_the_report(client, db):
    """Matching is on fulfilment_type = 'pdf_report' (CT-002): a watchlist redemption that names the
    product (the API accepts a product on any item) opens nothing."""
    user_id, headers = await member_with_coins(client, db)
    r = await client.post(f"{API}/redemptions", headers=headers, json={
        "item_code": "watchlist_3", "product": X, "request_id": uuid.uuid4().hex})
    assert r.status_code == 201 and r.json()["status"] == "fulfilled", r.text
    row = await db.get(Redemption, uuid.UUID(r.json()["id"]))
    assert row.product_id is not None  # the product is recorded on the watchlist redemption
    r = await client.get(f"{API}/products/{X}/report", headers=headers)
    assert r.status_code == 403 and r.json() == {"detail": "report_not_redeemed"}
