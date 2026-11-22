"""Redemptions (TC-P1-017, WO-019, D13): two items on sale in phase one; nothing is left `processing`."""
import psycopg
import pytest

from conftest import ROOT, make_product, make_user, one, savepoint_raises, up_part

MIGRATION = ROOT / "db" / "migrations" / "20261122140000_redemptions_phase_one.sql"


def funded_user(db, coins_rule="level2_verified"):
    u = make_user(db)
    db.execute("SELECT coin_earn(%s, %s, %s)", (u, coins_rule, f"fund:{u}"))
    db.execute("UPDATE coin_ledger_entries SET confirmable_at = now() - interval '1 s' WHERE user_id = %s", (u,))
    db.execute("SELECT coin_confirm_due()")
    return u


def balance(db, u):
    return db.execute("SELECT confirmed_balance, lifetime_earned FROM coin_balances WHERE user_id = %s", (u,)).fetchone()


def stuck_redemption(db, u, item="hazard_export_100"):
    """A redemption of a phase-two item left `processing`, as the service used to leave them. The item is put
    back on sale inside this test's transaction only: the API can no longer reach this state."""
    db.execute("UPDATE redemption_items SET is_active = true WHERE code = %s", (item,))
    rid = one(db, "SELECT coin_redeem(%s, %s, %s)", (u, item, f"stuck:{u}:{item}"))
    assert one(db, "SELECT status FROM redemptions WHERE id = %s", (rid,)) == "processing"
    return rid


def test_only_the_hazard_report_and_extra_watches_are_on_sale(db):
    active = db.execute("SELECT code, fulfilment_type FROM redemption_items WHERE is_active ORDER BY code").fetchall()
    assert active == [("hazard_report_pdf", "pdf_report"), ("watchlist_3", "watchlist_slots")]
    assert one(db, "SELECT count(*) FROM redemption_items WHERE NOT is_active") == 4


LABEL_MIGRATION = ROOT / "db" / "migrations" / "20261122160000_hazard_report_printable_label.sql"


def test_the_hazard_report_is_labelled_printable_and_keeps_its_code_and_terms(db):
    """DEF-035: the report is a printable page, so the store label promises no PDF; only the label changed."""
    row = db.execute("SELECT code, name, cost_coins, fulfilment_type, duration, quantity, is_active "
                     "FROM redemption_items WHERE code = 'hazard_report_pdf'").fetchone()
    assert row == ("hazard_report_pdf", "Full hazard report (printable)", 50, "pdf_report", None, 1, True)
    assert one(db, "SELECT count(*) FROM redemption_items WHERE name ILIKE '%%PDF%%'") == 0


def test_the_label_migration_rolls_back_and_reapplies_cleanly(db):
    sql = LABEL_MIGRATION.read_text()
    label = "SELECT name FROM redemption_items WHERE code = 'hazard_report_pdf'"
    db.execute(sql.split("-- migrate:down", 1)[1])
    assert one(db, label) == "Full hazard report (PDF)"
    db.execute(up_part(sql))
    db.execute(up_part(sql))                                   # a second run changes nothing
    assert one(db, label) == "Full hazard report (printable)"


@pytest.mark.parametrize("item", ["api_boost_month", "early_access", "hazard_export_100", "subscription_10pct"])
def test_an_item_off_sale_cannot_be_redeemed(db, item):
    u = funded_user(db)
    savepoint_raises(db, "SELECT coin_redeem(%s, %s, 'k')", (u, item), match="inactive")
    assert balance(db, u) == (500, 500)


def test_refund_returns_the_coins_once_and_marks_the_redemption_refunded(db):
    u = funded_user(db)
    rid = stuck_redemption(db, u)
    assert balance(db, u) == (200, 500)
    spend = one(db, "SELECT ledger_entry_id FROM redemptions WHERE id = %s", (rid,))

    refund = one(db, "SELECT coin_refund_redemption(%s, 'test')", (rid,))
    assert balance(db, u) == (500, 500)                       # spendable again; lifetime earned untouched
    assert db.execute("SELECT entry_type, amount, status, reverses_entry_id FROM coin_ledger_entries WHERE id = %s",
                      (refund,)).fetchone() == ("refund", 300, "confirmed", spend)
    status, fulfilment = db.execute("SELECT status, fulfilment FROM redemptions WHERE id = %s", (rid,)).fetchone()
    assert status == "refunded" and fulfilment["refund"] == {"ledger_entry_id": str(refund), "reason": "test"}

    assert one(db, "SELECT coin_refund_redemption(%s, 'again')", (rid,)) == refund   # a second refund pays nothing
    assert balance(db, u) == (500, 500)
    assert one(db, "SELECT count(*) FROM coin_ledger_entries WHERE user_id = %s AND entry_type = 'refund'", (u,)) == 1


def test_a_failed_redemption_can_be_refunded(db):
    u = funded_user(db)
    rid = stuck_redemption(db, u)
    db.execute("UPDATE redemptions SET status = 'failed' WHERE id = %s", (rid,))
    db.execute("SELECT coin_refund_redemption(%s)", (rid,))
    assert balance(db, u) == (500, 500)


def test_a_fulfilled_redemption_is_not_refunded(db):
    u, p = funded_user(db), make_product(db)
    rid = one(db, "SELECT coin_redeem(%s, 'hazard_report_pdf', 'r1', %s)", (u, p))
    db.execute("UPDATE redemptions SET status = 'fulfilled', fulfilled_at = now() WHERE id = %s", (rid,))
    savepoint_raises(db, "SELECT coin_refund_redemption(%s)", (rid,), match="only processing or failed")
    assert balance(db, u) == (450, 500)


def test_a_redemption_that_granted_an_entitlement_is_not_refunded(db):
    u = funded_user(db)
    rid = one(db, "SELECT coin_redeem(%s, 'watchlist_3', 'w1')", (u,))
    db.execute("""INSERT INTO user_entitlements (user_id, source, redemption_id, entitlement, quantity)
                  VALUES (%s, 'redemption', %s, 'watchlist_slots', 3)""", (u, rid))
    savepoint_raises(db, "SELECT coin_refund_redemption(%s)", (rid,), match="delivered")
    assert balance(db, u) == (400, 500)


def test_an_unknown_redemption_is_refused(db):
    with pytest.raises(psycopg.Error) as ei:
        with db.transaction():
            db.execute("SELECT coin_refund_redemption(uuidv7())")
    assert ei.value.sqlstate == "TC013"


def test_the_migration_refunds_every_stuck_redemption_once(db):
    u, other = funded_user(db), funded_user(db)
    stuck = [stuck_redemption(db, u, "hazard_export_100"), stuck_redemption(db, other, "early_access")]
    kept = one(db, "SELECT coin_redeem(%s, 'watchlist_3', 'kept')", (u,))      # active item: not touched
    assert balance(db, u) == (100, 500) and balance(db, other) == (0, 500)

    db.execute(up_part(MIGRATION.read_text()))
    assert [one(db, "SELECT status FROM redemptions WHERE id = %s", (r,)) for r in stuck] == ["refunded", "refunded"]
    assert one(db, "SELECT status FROM redemptions WHERE id = %s", (kept,)) == "processing"
    assert balance(db, u) == (400, 500) and balance(db, other) == (500, 500)
    assert one(db, "SELECT count(*) FROM redemption_items WHERE is_active") == 2

    db.execute(up_part(MIGRATION.read_text()))                                 # running it again pays nothing
    assert balance(db, u) == (400, 500) and balance(db, other) == (500, 500)
