"""The coin store (WO-019, D13, CT-004): only the printable hazard report is on sale, each item redeemed
is fulfilled at once, an item off sale is refused before any spend, and nothing is ever left
`processing` — what cannot be fulfilled is refunded, once."""

import contextlib
import uuid

import pytest
from fastapi import HTTPException
from helpers import API, verified_user
from sqlalchemy import func, select, text

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


@contextlib.asynccontextmanager
async def on_sale(db, code: str):
    """Put an item on sale for one test and take it off again. The API answers from its own sessions,
    so the change is committed; the finally restores the reference data whatever the test does."""
    await db.execute(text("update redemption_items set is_active = true where code = :c"), {"c": code})
    await db.commit()
    try:
        yield
    finally:
        await db.execute(text("update redemption_items set is_active = false where code = :c"),
                         {"c": code})
        await db.commit()


async def ledger_count(db, user_id) -> int:
    return int(await db.scalar(select(func.count()).select_from(CoinLedgerEntry)
                               .where(CoinLedgerEntry.user_id == user_id)))


async def test_the_store_lists_only_the_printable_report(client, db):
    """CT-004: after DEF-117 the store holds exactly one item; the watchlist item is not listed."""
    _, headers = await member_with_coins(client, db)
    store = (await client.get(f"{API}/rewards", headers=headers)).json()["store"]
    assert [i["code"] for i in store] == ["hazard_report_pdf"]
    assert store[0]["kind"] == "pdf_report" and store[0]["needs_product"] is True
    active = (await db.execute(select(RedemptionItem.code).where(RedemptionItem.is_active)))
    assert {i["code"] for i in store} == set(active.scalars())


async def test_each_item_on_sale_is_fulfilled_when_redeemed(client, db):
    items = (await db.execute(select(RedemptionItem.code, RedemptionItem.fulfilment_type,
                                     RedemptionItem.cost_coins, RedemptionItem.quantity)
                              .where(RedemptionItem.is_active))).all()
    assert items
    for code, kind, cost, _ in items:
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


async def test_the_watchlist_item_is_fulfilled_with_slots_when_back_on_sale(client, db):
    """watchlist_3 is off sale until WO-033 builds watches; its fulfilment is kept for that day."""
    cost, quantity = (await db.execute(select(RedemptionItem.cost_coins, RedemptionItem.quantity)
                                       .where(RedemptionItem.code == "watchlist_3"))).one()
    async with on_sale(db, "watchlist_3"):
        user_id, headers = await member_with_coins(client, db)
        r = await client.post(f"{API}/redemptions", headers=headers,
                              json={"item_code": "watchlist_3", "request_id": "one"})
        assert r.status_code == 201 and r.json()["status"] == "fulfilled", r.text
        assert await confirmed(client, headers) == START - int(cost)
        [row] = await redemptions_of(db, user_id)
        assert row.status == "fulfilled" and row.fulfilled_at is not None
        grant = (await db.execute(select(UserEntitlement).where(
            UserEntitlement.redemption_id == row.id))).scalar_one()
        assert grant.entitlement == "watchlist_slots" and grant.quantity == quantity


async def test_the_watchlist_item_is_not_on_sale_and_takes_nothing(client, db):
    """DEF-117 / CT-004: 409 item_not_on_sale, no spend, no redemption, no ledger entry."""
    user_id, headers = await member_with_coins(client, db)
    entries = await ledger_count(db, user_id)
    r = await client.post(f"{API}/redemptions", headers=headers,
                          json={"item_code": "watchlist_3", "request_id": "w"})
    assert r.status_code == 409 and r.json() == {"detail": "item_not_on_sale"}, r.text
    assert await confirmed(client, headers) == START
    assert await redemptions_of(db, user_id) == []
    assert await ledger_count(db, user_id) == entries


async def test_an_item_off_sale_is_refused_and_takes_nothing(client, db):
    off = (await db.execute(select(RedemptionItem.code, RedemptionItem.fulfilment_type)
                            .where(~RedemptionItem.is_active)))
    off = list(off.all())
    assert {c for c, _ in off} >= {"watchlist_3"}  # D13's four and, since DEF-117, the watchlist
    user_id, headers = await member_with_coins(client, db)
    entries = await ledger_count(db, user_id)
    for code, _ in off:
        # No product is sent: an off-sale report item is still 409, as 422 is only for items on sale.
        r = await client.post(f"{API}/redemptions", headers=headers,
                              json={"item_code": code, "request_id": code})
        assert r.status_code == 409 and r.json()["detail"] == "item_not_on_sale", (code, r.text)
    assert await confirmed(client, headers) == START
    assert await redemptions_of(db, user_id) == []
    assert await ledger_count(db, user_id) == entries


async def test_an_unknown_item_is_not_found(client, db):
    user_id, headers = await member_with_coins(client, db)
    r = await client.post(f"{API}/redemptions", headers=headers,
                          json={"item_code": "no_such_item", "request_id": "u"})
    assert r.status_code == 404 and r.json() == {"detail": "item_not_found"}, r.text
    assert await confirmed(client, headers) == START
    assert await redemptions_of(db, user_id) == []


async def test_an_item_taken_off_sale_mid_request_is_refused_by_the_database(client, db):
    """The backstop: the service read the item on sale, then it went off sale before coin_redeem
    ran. coin_redeem's TC011 maps to the same 409 item_not_on_sale and nothing is spent."""
    code = f"test_race_{uuid.uuid4().hex[:8]}"
    db.add(RedemptionItem(code=code, name="Going off sale", cost_coins=30,
                          fulfilment_type="watchlist_slots", quantity=1, is_active=True))
    await db.commit()
    try:
        user_id, headers = await member_with_coins(client, db)
        assert (await db.get(RedemptionItem, code)).is_active  # this session holds it as on sale
        from app.core.db import SessionLocal
        async with SessionLocal() as other:
            await other.execute(text("update redemption_items set is_active = false where code = :c"),
                                {"c": code})
            await other.commit()
        with pytest.raises(HTTPException) as refused:
            await rewards.redeem(db, user_id, code, f"{user_id}:race", None)
        assert (refused.value.status_code, refused.value.detail) == (409, "item_not_on_sale")
        await db.rollback()
        assert await confirmed(client, headers) == START
        assert await redemptions_of(db, user_id) == []
    finally:
        await db.execute(text("update redemption_items set is_active = false where code = :c"),
                         {"c": code})
        await db.commit()


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
