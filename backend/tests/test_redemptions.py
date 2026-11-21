"""The coin store (WO-019, D13): only phase-one items are on sale, each one redeemed is fulfilled at
once, and nothing is ever left `processing` — what cannot be fulfilled is refunded, once."""

import uuid

from helpers import API, verified_user
from sqlalchemy import select, text

from app.models import CoinLedgerEntry, Redemption, RedemptionItem, User, UserEntitlement
from app.modules.rewards import service as rewards

START = 105  # level1_verified 100 + the first day's login_streak 5, confirmed at once in tests


async def member_with_coins(client, db):
    email, _, headers = await verified_user(client)
    await db.commit()  # a fresh transaction, so now() is after the sign-up's coins
    await rewards.confirm_due(db)
    await db.commit()
    assert (await client.get(f"{API}/coins", headers=headers)).json()["confirmed"] == START
    user_id = (await db.execute(select(User.id).where(User.email == email))).scalar_one()
    return user_id, headers


async def confirmed(client, headers) -> int:
    return (await client.get(f"{API}/coins", headers=headers)).json()["confirmed"]


async def redemptions_of(db, user_id) -> list[Redemption]:
    db.expire_all()
    return list((await db.execute(select(Redemption).where(Redemption.user_id == user_id)))
                .scalars())


async def test_the_store_lists_only_the_phase_one_items(client, db):
    _, headers = await member_with_coins(client, db)
    store = (await client.get(f"{API}/rewards", headers=headers)).json()["store"]
    assert {i["kind"] for i in store} == {"pdf_report", "watchlist_slots"}
    active = (await db.execute(select(RedemptionItem.code).where(RedemptionItem.is_active)))
    assert {i["code"] for i in store} == set(active.scalars())


async def test_each_item_on_sale_is_fulfilled_when_redeemed(client, db):
    items = (await db.execute(select(RedemptionItem.code, RedemptionItem.fulfilment_type,
                                     RedemptionItem.cost_coins, RedemptionItem.quantity)
                              .where(RedemptionItem.is_active))).all()
    assert items
    for code, kind, cost, quantity in items:
        user_id, headers = await member_with_coins(client, db)
        body = {"item_code": code, "request_id": "one"}
        if kind == "pdf_report":  # the hazard report is of a product
            body["product"] = "aquablend-900"
        r = await client.post(f"{API}/redemptions", headers=headers, json=body)
        assert r.status_code == 201, (code, r.text)
        assert r.json()["status"] == "fulfilled"
        assert await confirmed(client, headers) == START - int(cost)
        [row] = await redemptions_of(db, user_id)
        assert row.status == "fulfilled" and row.fulfilled_at is not None
        if kind == "watchlist_slots":
            grant = (await db.execute(select(UserEntitlement).where(
                UserEntitlement.redemption_id == row.id))).scalar_one()
            assert grant.entitlement == "watchlist_slots" and grant.quantity == quantity


async def test_an_item_off_sale_is_refused_and_takes_nothing(client, db):
    off = (await db.execute(select(RedemptionItem.code).where(~RedemptionItem.is_active)))
    off = list(off.scalars())
    assert off  # the four items D13 took off sale
    user_id, headers = await member_with_coins(client, db)
    for code in off:
        r = await client.post(f"{API}/redemptions", headers=headers,
                              json={"item_code": code, "request_id": code})
        assert r.status_code == 404 and r.json()["detail"] == "item_not_found", (code, r.text)
    assert await confirmed(client, headers) == START
    assert await redemptions_of(db, user_id) == []


async def test_an_item_that_cannot_be_fulfilled_is_refunded_once(client, db):
    # Reference data: an item on sale whose fulfilment is not built. The API cannot create one; this
    # is the state WO-019 guards against should such an item ever be put back on sale.
    code = f"test_unbuilt_{uuid.uuid4().hex[:8]}"
    db.add(RedemptionItem(code=code, name="Not built yet", cost_coins=30,
                          fulfilment_type="data_export", quantity=1, is_active=True))
    await db.commit()
    try:
        user_id, headers = await member_with_coins(client, db)
        body = {"item_code": code, "request_id": "x"}
        r = await client.post(f"{API}/redemptions", headers=headers, json=body)
        assert r.status_code == 409 and r.json()["detail"] == "item_not_available", r.text
        assert await confirmed(client, headers) == START  # spent and given back

        [row] = await redemptions_of(db, user_id)
        assert row.status == "refunded" and row.fulfilment["refund"]["ledger_entry_id"]
        # A retried click spends nothing more and refunds nothing more.
        again = await client.post(f"{API}/redemptions", headers=headers, json=body)
        assert again.status_code == 409 and again.json()["id"] == str(row.id)
        # Nor does a second refund through the database's own function.
        first = row.fulfilment["refund"]["ledger_entry_id"]
        second = await db.scalar(text("select coin_refund_redemption(:r)"), {"r": row.id})
        await db.commit()
        assert str(second) == first

        assert await confirmed(client, headers) == START
        entries = (await db.execute(select(CoinLedgerEntry.entry_type, CoinLedgerEntry.amount)
                                    .where(CoinLedgerEntry.reference_id == row.id))).all()
        assert sorted((t, int(a)) for t, a in entries) == [("refund", 30), ("spend", -30)]
        assert [x.status for x in await redemptions_of(db, user_id)] == ["refunded"]
    finally:
        await db.execute(text("update redemption_items set is_active = false where code = :c"),
                         {"c": code})
        await db.commit()
