"""DEF-117, WO-059: watchlist_3 goes off sale and its buyers are refunded by coin_refund_withdrawn_redemption().

The general coin_refund_redemption() still refuses anything delivered (test_redemptions.py). The new function
reverses only a fulfilled redemption of an item that is off sale, whose fulfilment is watchlist_slots and
whose entitlement no watch uses, and deletes that entitlement in the same call.
"""
import psycopg
import pytest

from conftest import ROOT, make_product, make_user, one, savepoint_raises, up_part

MIGRATION = ROOT / "db" / "migrations" / "20261123130000_watchlist_off_sale_refund.sql"


def funded_user(db):
    u = make_user(db)
    db.execute("SELECT coin_earn(%s, 'level2_verified', %s)", (u, f"fund:{u}"))
    db.execute("UPDATE coin_ledger_entries SET confirmable_at = now() - interval '1 s' WHERE user_id = %s", (u,))
    db.execute("SELECT coin_confirm_due()")
    return u


def balance(db, u):
    return db.execute("SELECT confirmed_balance, lifetime_earned FROM coin_balances WHERE user_id = %s", (u,)).fetchone()


def bought_watchlist(db, u, key="w"):
    """A watchlist_3 redemption as the service fulfilled it before WO-059 (entitlement + fulfilled), then the
    item taken off sale again, as the migration leaves it. Returns (redemption, entitlement)."""
    db.execute("UPDATE redemption_items SET is_active = true WHERE code = 'watchlist_3'")
    rid = one(db, "SELECT coin_redeem(%s, 'watchlist_3', %s)", (u, f"{key}:{u}"))
    ent = one(db, """INSERT INTO user_entitlements (user_id, source, redemption_id, entitlement, quantity)
                     VALUES (%s, 'redemption', %s, 'watchlist_slots', 3) RETURNING id""", (u, rid))
    db.execute("UPDATE redemptions SET status = 'fulfilled', fulfilled_at = now() WHERE id = %s", (rid,))
    db.execute("UPDATE redemption_items SET is_active = false WHERE code = 'watchlist_3'")
    return rid, ent


def bought_report(db, u):
    rid = one(db, "SELECT coin_redeem(%s, 'hazard_report_pdf', %s, %s)", (u, f"r:{u}", make_product(db)))
    db.execute("UPDATE redemptions SET status = 'fulfilled', fulfilled_at = now(), fulfilment = '{}' WHERE id = %s",
               (rid,))
    return rid


def ledger(db, u):
    return db.execute("SELECT id, entry_type, amount, status, reverses_entry_id FROM coin_ledger_entries "
                      "WHERE user_id = %s ORDER BY created_at, id", (u,)).fetchall()


def test_refund_restores_the_spend_revokes_the_slots_and_keeps_the_record(db):
    u = funded_user(db)
    rid, ent = bought_watchlist(db, u)
    assert balance(db, u) == (400, 500)
    spend = one(db, "SELECT ledger_entry_id FROM redemptions WHERE id = %s", (rid,))
    before = ledger(db, u)

    refund = one(db, "SELECT coin_refund_withdrawn_redemption(%s, 'test')", (rid,))
    assert balance(db, u) == (500, 500)                       # spendable again; lifetime earned untouched
    assert db.execute("SELECT entry_type, amount, status, reverses_entry_id, reference_type, reference_id "
                      "FROM coin_ledger_entries WHERE id = %s", (refund,)).fetchone() == \
        ("refund", 100, "confirmed", spend, "redemption", rid)
    assert ledger(db, u)[:-1] == before                       # earlier entries untouched; one entry added
    assert one(db, "SELECT count(*) FROM user_entitlements WHERE redemption_id = %s", (rid,)) == 0

    status, fulfilled_at, fulfilment = db.execute(
        "SELECT status, fulfilled_at, fulfilment FROM redemptions WHERE id = %s", (rid,)).fetchone()
    assert status == "refunded" and fulfilled_at is not None  # it was delivered, and the record says so
    assert fulfilment["refund"]["ledger_entry_id"] == str(refund) and fulfilment["refund"]["reason"] == "test"
    revoked = fulfilment["refund"]["revoked_entitlements"]
    assert [(e["id"], e["entitlement"], e["quantity"]) for e in revoked] == [(str(ent), "watchlist_slots", 3)]


def test_a_second_refund_pays_nothing(db):
    u = funded_user(db)
    rid, _ = bought_watchlist(db, u)
    refund = one(db, "SELECT coin_refund_withdrawn_redemption(%s)", (rid,))
    assert one(db, "SELECT coin_refund_withdrawn_redemption(%s, 'again')", (rid,)) == refund
    assert one(db, "SELECT coin_refund_redemption(%s)", (rid,)) == refund      # nor through the other refund
    assert balance(db, u) == (500, 500)
    assert one(db, "SELECT count(*) FROM coin_ledger_entries WHERE user_id = %s AND entry_type = 'refund'", (u,)) == 1


def test_the_refund_entry_is_append_only(db):
    u = funded_user(db)
    rid, _ = bought_watchlist(db, u)
    refund = one(db, "SELECT coin_refund_withdrawn_redemption(%s)", (rid,))
    savepoint_raises(db, "UPDATE coin_ledger_entries SET amount = 1 WHERE id = %s", (refund,))
    savepoint_raises(db, "DELETE FROM coin_ledger_entries WHERE id = %s", (refund,))


def test_a_delivered_hazard_report_is_refused_on_or_off_sale(db):
    u = funded_user(db)
    rid = bought_report(db, u)
    savepoint_raises(db, "SELECT coin_refund_withdrawn_redemption(%s)", (rid,), match="is on sale")
    db.execute("UPDATE redemption_items SET is_active = false WHERE code = 'hazard_report_pdf'")  # this test only
    savepoint_raises(db, "SELECT coin_refund_withdrawn_redemption(%s)", (rid,), match="delivers pdf_report")
    assert balance(db, u) == (450, 500)
    assert one(db, "SELECT status FROM redemptions WHERE id = %s", (rid,)) == "fulfilled"


def test_a_watchlist_redemption_is_refused_while_the_item_is_on_sale(db):
    u = funded_user(db)
    rid, _ = bought_watchlist(db, u)
    db.execute("UPDATE redemption_items SET is_active = true WHERE code = 'watchlist_3'")    # WO-033 re-lists it
    savepoint_raises(db, "SELECT coin_refund_withdrawn_redemption(%s)", (rid,), match="is on sale")
    assert balance(db, u) == (400, 500)
    assert one(db, "SELECT count(*) FROM user_entitlements WHERE redemption_id = %s", (rid,)) == 1


def test_a_redemption_that_is_not_fulfilled_is_refused(db):
    u = funded_user(db)
    db.execute("UPDATE redemption_items SET is_active = true WHERE code = 'watchlist_3'")
    rid = one(db, "SELECT coin_redeem(%s, 'watchlist_3', 'p')", (u,))
    db.execute("UPDATE redemption_items SET is_active = false WHERE code = 'watchlist_3'")
    savepoint_raises(db, "SELECT coin_refund_withdrawn_redemption(%s)", (rid,), match="use coin_refund_redemption")
    assert balance(db, u) == (400, 500)


def test_slots_in_use_by_a_watch_are_not_taken_back(db):
    u = funded_user(db)
    rid, ent = bought_watchlist(db, u)
    db.execute("INSERT INTO product_watches (user_id, product_id, entitlement_id) VALUES (%s, %s, %s)",
               (u, make_product(db), ent))
    savepoint_raises(db, "SELECT coin_refund_withdrawn_redemption(%s)", (rid,), match="in use by a product watch")
    assert balance(db, u) == (400, 500)
    assert one(db, "SELECT count(*) FROM user_entitlements WHERE id = %s", (ent,)) == 1


def test_an_unknown_redemption_is_refused(db):
    with pytest.raises(psycopg.Error) as ei:
        with db.transaction():
            db.execute("SELECT coin_refund_withdrawn_redemption(uuidv7())")
    assert ei.value.sqlstate == "TC013"


def test_fulfilled_at_is_kept_only_by_a_fulfilled_or_refunded_redemption(db):
    """redemptions_chk1 as revised by the migration."""
    u = funded_user(db)
    rid = bought_report(db, u)
    db.execute("UPDATE redemptions SET status = 'refunded' WHERE id = %s", (rid,))   # delivered, then refunded
    savepoint_raises(db, "UPDATE redemptions SET status = 'processing' WHERE id = %s", (rid,), match="redemptions_chk1")
    savepoint_raises(db, "UPDATE redemptions SET status = 'failed' WHERE id = %s", (rid,), match="redemptions_chk1")
    savepoint_raises(db, "UPDATE redemptions SET status = 'fulfilled', fulfilled_at = NULL WHERE id = %s", (rid,),
                     match="redemptions_chk1")


def test_the_migration_takes_watchlist_off_sale_and_refunds_every_buyer_once(db):
    a, b, c = funded_user(db), funded_user(db), funded_user(db)
    bought = [bought_watchlist(db, a)[0], bought_watchlist(db, b)[0]]
    report = bought_report(db, c)
    db.execute("UPDATE redemption_items SET is_active = true WHERE code = 'watchlist_3'")    # as before WO-059
    assert [balance(db, u) for u in (a, b, c)] == [(400, 500), (400, 500), (450, 500)]

    db.execute(up_part(MIGRATION.read_text()))
    assert db.execute("SELECT code FROM redemption_items WHERE is_active").fetchall() == [("hazard_report_pdf",)]
    assert [one(db, "SELECT status FROM redemptions WHERE id = %s", (r,)) for r in bought] == ["refunded"] * 2
    assert one(db, "SELECT count(*) FROM user_entitlements WHERE redemption_id = ANY(%s)", (bought,)) == 0
    assert one(db, "SELECT status FROM redemptions WHERE id = %s", (report,)) == "fulfilled"
    assert [balance(db, u) for u in (a, b, c)] == [(500, 500), (500, 500), (450, 500)]

    db.execute(up_part(MIGRATION.read_text()))                                 # running it again pays nothing
    assert [balance(db, u) for u in (a, b, c)] == [(500, 500), (500, 500), (450, 500)]
    assert one(db, "SELECT count(*) FROM coin_ledger_entries WHERE entry_type = 'refund' AND user_id = ANY(%s)",
               ([a, b, c],)) == 2


def test_the_migration_rolls_back_and_reapplies(db):
    sql = MIGRATION.read_text()
    chk = ("SELECT pg_get_constraintdef(oid) FROM pg_constraint "
           "WHERE conname = 'redemptions_chk1' AND conrelid = 'redemptions'::regclass")
    db.execute(sql.split("-- migrate:down", 1)[1])            # no refunded row kept fulfilled_at here
    assert one(db, "SELECT to_regprocedure('coin_refund_withdrawn_redemption(uuid, text)')") is None
    assert "= (fulfilled_at IS NOT NULL)" in one(db, chk)
    assert one(db, "SELECT is_active FROM redemption_items WHERE code = 'watchlist_3'") is False   # stays off sale
    db.execute(up_part(sql))
    assert "'refunded'" in one(db, chk)


def test_the_rollback_keeps_the_revised_check_when_a_refunded_redemption_kept_fulfilled_at(db):
    u = funded_user(db)
    rid, _ = bought_watchlist(db, u)
    db.execute("SELECT coin_refund_withdrawn_redemption(%s)", (rid,))
    sql = MIGRATION.read_text()
    db.execute(sql.split("-- migrate:down", 1)[1])
    assert one(db, "SELECT status FROM redemptions WHERE id = %s", (rid,)) == "refunded"
    assert "'refunded'" in one(db, "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                                   "WHERE conname = 'redemptions_chk1' AND conrelid = 'redemptions'::regclass")
