"""The full hazard report is a paid entitlement (CT-002, DEF-035): only a member holding a fulfilled
hazard-report redemption of that product opens it. Nobody else learns anything about who bought it."""

import uuid

from helpers import API, verified_user
from sqlalchemy import select, text

from app.models import Redemption, User
from app.modules.rewards import service as rewards

X, Y = "aquablend-900", "voltpro-65w-charger"


async def member_with_coins(client, db):
    email, _, headers = await verified_user(client)
    await db.commit()  # a fresh transaction, so now() is after the sign-up's coins
    await rewards.confirm_due(db)
    await db.commit()
    user_id = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
    return user_id, headers


async def redeem_report(client, headers, slug: str) -> dict:
    r = await client.post(f"{API}/redemptions", headers=headers, json={
        "item_code": "hazard_report_pdf", "product": slug, "request_id": uuid.uuid4().hex})
    assert r.status_code == 201 and r.json()["status"] == "fulfilled", r.text
    return r.json()


def refused(r) -> bool:
    return r.status_code == 403 and r.json() == {"detail": "report_not_redeemed"}


async def test_a_visitor_is_asked_to_sign_in(client):
    r = await client.get(f"{API}/products/{X}/report")
    assert r.status_code == 401


async def test_an_unknown_product_is_not_found(client):
    _, _, headers = await verified_user(client)
    for ref in ("no-such-product", str(uuid.uuid4())):
        r = await client.get(f"{API}/products/{ref}/report", headers=headers)
        assert r.status_code == 404 and r.json()["detail"] == "product_not_found"


async def test_a_member_who_has_not_redeemed_it_is_refused(client):
    _, _, headers = await verified_user(client)
    assert refused(await client.get(f"{API}/products/{X}/report", headers=headers))


async def test_another_members_redemption_opens_nothing_and_reveals_nothing(client, db):
    _, nobody = await member_with_coins(client, db)
    before = await client.get(f"{API}/products/{Y}/report", headers=nobody)
    _, buyer = await member_with_coins(client, db)
    await redeem_report(client, buyer, Y)
    _, other = await member_with_coins(client, db)
    after = await client.get(f"{API}/products/{Y}/report", headers=other)
    # The same answer whether nobody or another member bought it.
    assert refused(before) and refused(after)
    assert (before.status_code, before.json()) == (after.status_code, after.json())


async def test_the_buyer_opens_the_report_of_that_product_only(client, db):
    user_id, headers = await member_with_coins(client, db)
    bought = await redeem_report(client, headers, X)
    r = await client.get(f"{API}/products/{X}/report", headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers["Cache-Control"] == "private, no-store"
    body = r.json()
    assert set(body) == {"product", "passport", "redemption"}
    assert body["product"] == (await client.get(f"{API}/products/{X}")).json()
    assert body["passport"] == (await client.get(f"{API}/products/{X}/passport")).json()
    row = await db.get(Redemption, uuid.UUID(bought["id"]))
    assert body["redemption"] == {"id": bought["id"], "fulfilled_at": row.fulfilled_at.isoformat()}
    # By id as well as by slug.
    by_id = await client.get(f"{API}/products/{body['product']['id']}/report", headers=headers)
    assert by_id.status_code == 200 and by_id.json()["redemption"]["id"] == bought["id"]
    # Buying one product's report does not open another's.
    assert refused(await client.get(f"{API}/products/{Y}/report", headers=headers))


async def test_a_refunded_redemption_does_not_open_it(client, db):
    user_id, headers = await member_with_coins(client, db)
    pid = (await client.get(f"{API}/products/{X}")).json()["id"]
    # A hazard-report redemption that was not delivered and was refunded, through the database's
    # own functions (the API never leaves a pdf_report undelivered).
    redemption_id = await db.scalar(rewards.REDEEM, {"user": user_id, "item": "hazard_report_pdf",
                                                     "key": f"{user_id}:refund-me", "product": pid})
    await db.scalar(text("select coin_refund_redemption(:r, 'test')"), {"r": redemption_id})
    await db.commit()
    assert (await db.get(Redemption, redemption_id)).status == "refunded"
    assert refused(await client.get(f"{API}/products/{X}/report", headers=headers))
