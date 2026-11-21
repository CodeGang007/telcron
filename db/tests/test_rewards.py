"""TelCoins ledger (TC-P1-016/017/018): correctness, limits, fraud and concurrency."""
import threading
import uuid

import psycopg
import pytest

from conftest import make_product, make_user, one, savepoint_raises


def bal(db, u):
    return db.execute("SELECT confirmed_balance, pending_balance, frozen_balance, lifetime_earned FROM coin_balances WHERE user_id = %s",
                      (u,)).fetchone()


def earn(db, u, rule, key, subject=None):
    return one(db, "SELECT coin_earn(%s, %s, %s, 'product', %s)", (u, rule, key, subject))


def confirm_now(db, u):
    # fast-forward the fraud window for this user's pending entries (allowed column), then sweep
    db.execute("UPDATE coin_ledger_entries SET confirmable_at = now() - interval '1 s' WHERE user_id = %s AND status = 'pending'", (u,))
    return one(db, "SELECT coin_confirm_due()")


def test_earn_pending_then_confirmed(db):
    u = make_user(db)
    e = earn(db, u, "level1_verified", f"l1:{u}")
    assert one(db, "SELECT status FROM coin_ledger_entries WHERE id = %s", (e,)) == "pending"
    assert bal(db, u) == (0, 100, 0, 0)                 # pending coins are not spendable
    savepoint_raises(db, "SELECT coin_spend(%s, 10, 'too-early')", (u,), match="insufficient")
    confirm_now(db, u)
    assert bal(db, u) == (100, 0, 0, 100)


def test_idempotent_and_one_time_bonus(db):
    u = make_user(db)
    e1 = earn(db, u, "level1_verified", "k1")
    assert earn(db, u, "level1_verified", "k1") == e1   # retry with same key = same entry
    assert earn(db, u, "level1_verified", "k2") is None # lifetime limit 1
    assert bal(db, u)[1] == 100


def test_review_reward_capped_per_product(db):
    u, p = make_user(db), make_product(db)
    awarded = [earn(db, u, "review", f"review:{i}", p) for i in range(7)]
    assert sum(a is not None for a in awarded) == 5     # 10 coins × 5 reviews per product
    assert earn(db, u, "review", "review:other", make_product(db)) is not None


def test_daily_cap_500(db):
    u = make_user(db)
    db.execute("UPDATE app_settings SET value = '1000' WHERE key = 'rewards.rapid_fire_threshold'")
    total = 0
    for i in range(40):                                  # 40 photos × 15 = 600 > cap
        if earn(db, u, "photo", f"photo:{i}"):
            total += 1
    amounts = [r[0] for r in db.execute("SELECT amount FROM coin_ledger_entries WHERE user_id = %s AND entry_type = 'earn'", (u,))]
    assert sum(amounts) == 500 and amounts[-1] == 5      # last award trimmed to the remaining cap
    assert earn(db, u, "level1_verified", "l1") is not None   # one-time bonuses don't count toward the cap


def test_level_bonus_from_lifetime_earned(db):
    u = make_user(db)
    earn(db, u, "level2_verified", "l2")                 # +500 → Inspector after confirmation
    confirm_now(db, u)
    assert one(db, "SELECT title FROM telcron_reward_level(%s)", (u,)) == "Inspector"
    earn(db, u, "photo", "photo:1")                      # 15 × 5% = 0.75 → floors to no bonus
    assert one(db, "SELECT count(*) FROM coin_ledger_entries WHERE user_id = %s AND entry_type = 'level_bonus'", (u,)) == 0
    earn(db, u, "referral", "ref:1", make_product(db))   # 50 × 5% = 2
    assert one(db, "SELECT sum(amount) FROM coin_ledger_entries WHERE user_id = %s AND entry_type = 'level_bonus'", (u,)) == 2
    db.execute("SELECT coin_spend(%s, 500, 'spend-all')", (u,))
    assert one(db, "SELECT title FROM telcron_reward_level(%s)", (u,)) == "Inspector"   # spending never lowers level


def test_spend_and_redeem(db):
    u, p = make_user(db), make_product(db)
    earn(db, u, "level1_verified", "l1")
    confirm_now(db, u)
    rid = one(db, "SELECT coin_redeem(%s, 'hazard_report_pdf', 'req-1', %s)", (u, p))
    assert one(db, "SELECT coin_redeem(%s, 'hazard_report_pdf', 'req-1', %s)", (u, p)) == rid   # idempotent
    assert bal(db, u)[0] == 50
    assert one(db, "SELECT amount FROM coin_ledger_entries l JOIN redemptions r ON r.ledger_entry_id = l.id WHERE r.id = %s", (rid,)) == -50
    savepoint_raises(db, "SELECT coin_redeem(%s, 'watchlist_3', 'req-2')", (u,), match="insufficient")   # costs 100


def test_clawback_confirmed_goes_into_debt_once(db):
    u = make_user(db)
    e = earn(db, u, "level1_verified", "l1")
    confirm_now(db, u)
    db.execute("SELECT coin_spend(%s, 80, 's1')", (u,))
    c1 = one(db, "SELECT coin_clawback(%s)", (e,))
    assert one(db, "SELECT coin_clawback(%s)", (e,)) == c1                 # no double clawback
    assert bal(db, u)[0] == -80 and bal(db, u)[3] == 0                     # debt; level progress removed
    savepoint_raises(db, """INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, reverses_entry_id, idempotency_key)
                            VALUES (%s, 'clawback', -100, 'confirmed', %s, 'manual-dup')""", (u, e),
                     match="coin_ledger_entries_u1_uidx")


def test_clawback_pending_reverses_in_place(db):
    u = make_user(db)
    e = earn(db, u, "level1_verified", "l1")
    assert one(db, "SELECT coin_clawback(%s)", (e,)) is None
    assert one(db, "SELECT status FROM coin_ledger_entries WHERE id = %s", (e,)) == "reversed"
    assert bal(db, u) == (0, 0, 0, 0)


def test_ledger_is_immutable_and_transitions_are_valid(db):
    u = make_user(db)
    e = earn(db, u, "level1_verified", "l1")
    savepoint_raises(db, "UPDATE coin_ledger_entries SET amount = 1000 WHERE id = %s", (e,), match="append-only")
    savepoint_raises(db, "DELETE FROM coin_ledger_entries WHERE id = %s", (e,), match="append-only")
    confirm_now(db, u)
    savepoint_raises(db, "UPDATE coin_ledger_entries SET status = 'pending' WHERE id = %s", (e,), match="cannot move")
    savepoint_raises(db, """INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, idempotency_key)
                            VALUES (%s, 'spend', 10, 'confirmed', 'bad-sign')""", (u,), match="coin_ledger_entries_chk3")
    savepoint_raises(db, """INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, idempotency_key)
                            VALUES (%s, 'spend', -10, 'pending', 'pending-spend')""", (u,),
                     match="coin_ledger_entries_chk")


def test_rapid_fire_hold_freezes_then_resolves(db):
    u, admin = make_user(db), make_user(db)
    db.execute("UPDATE app_settings SET value = '5' WHERE key = 'rewards.rapid_fire_threshold'")
    for i in range(7):
        earn(db, u, "photo", f"burst:{i}")
    hold = one(db, "SELECT id FROM fraud_holds WHERE user_id = %s AND status = 'open'", (u,))
    assert hold is not None
    c, pnd, frz, _ = bal(db, u)
    assert pnd == 0 and frz == 7 * 15
    savepoint_raises(db, "SELECT coin_spend(%s, 1, 'x')", (u,), match="insufficient")
    db.execute("SELECT coin_resolve_hold(%s, true, %s)", (hold, admin))
    assert bal(db, u) == (0, 0, 0, 0)
    assert one(db, "SELECT count(*) FROM coin_ledger_entries WHERE user_id = %s AND status = 'reversed'", (u,)) == 7


def test_balances_rebuild_from_ledger(db):
    u = make_user(db)
    e = earn(db, u, "level2_verified", "l2")
    confirm_now(db, u)
    earn(db, u, "photo", "p1")
    db.execute("SELECT coin_spend(%s, 120, 's')", (u,))
    db.execute("SELECT coin_clawback(%s)", (e,))
    derived = db.execute("""
        SELECT coalesce(sum(amount) FILTER (WHERE status = 'confirmed'), 0),
               coalesce(sum(amount) FILTER (WHERE status = 'pending'), 0)
          FROM coin_ledger_entries WHERE user_id = %s""", (u,)).fetchone()
    assert derived == bal(db, u)[:2]


def test_concurrent_spends_cannot_double_spend(committed, database):
    """Two connections race to spend 80 of a 100-coin balance: exactly one must win."""
    c = committed
    u = make_user(c)
    c.execute("SELECT coin_earn(%s, 'level1_verified', %s)", (u, f"race-l1-{u}"))
    c.execute("UPDATE coin_ledger_entries SET confirmable_at = now() - interval '1 s' WHERE user_id = %s", (u,))
    c.execute("SELECT coin_confirm_due()")
    results, barrier = [], threading.Barrier(2)

    def spend(tag):
        with psycopg.connect(database) as conn:
            try:
                barrier.wait()
                conn.execute("SELECT coin_spend(%s, 80, %s)", (u, f"race-{tag}-{uuid.uuid4()}"))
                conn.commit()
                results.append("ok")
            except psycopg.Error as e:
                conn.rollback()
                results.append("insufficient" if "insufficient" in str(e) else str(e))

    threads = [threading.Thread(target=spend, args=(i,)) for i in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    try:
        assert sorted(results) == ["insufficient", "ok"], results
        assert one(c, "SELECT confirmed_balance FROM coin_balances WHERE user_id = %s", (u,)) == 20
    finally:
        c.execute("SELECT set_config('telcron.allow_purge', 'on', false)")
        c.execute("DELETE FROM coin_ledger_entries WHERE user_id = %s", (u,))
        c.execute("DELETE FROM coin_balances WHERE user_id = %s", (u,))
        c.execute("DELETE FROM users WHERE id = %s", (u,))
        c.execute("SELECT set_config('telcron.allow_purge', 'off', false)")
