"""Risk events, timeline fan-out (TC-P1-010/029), feed (TC-P1-004/007), pricing (TC-P1-024)."""
from conftest import make_asset, make_product, make_recall, make_screening, make_user, one, savepoint_raises


def _hold(db, user, product):
    return one(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'search', 'active') RETURNING id",
               (user, product))


def _recall_event(db, product, recall):
    s = make_screening(db, product, verdict="match", recall_id=recall)
    return one(db, """INSERT INTO risk_events (product_id, event_type, severity, screening_id, recall_id, title)
                      VALUES (%s, 'recall_match', 'high', %s, %s, 'Recalled') RETURNING id""", (product, s, recall))


def test_rescreen_does_not_duplicate_risk_events(db):
    p, r = make_product(db), make_recall(db)
    _recall_event(db, p, r)
    s2 = make_screening(db, p, verdict="match", recall_id=r)          # tomorrow's re-screen, same recall
    savepoint_raises(db, """INSERT INTO risk_events (product_id, event_type, severity, screening_id, recall_id, title)
                            VALUES (%s, 'recall_match', 'high', %s, %s, 'Recalled again')""", (p, s2, r), match="risk_events_u1_uidx")


def test_event_type_requires_its_cause(db):
    p = make_product(db)
    savepoint_raises(db, "INSERT INTO risk_events (product_id, event_type, severity, title) VALUES (%s, 'recall_match', 'high', 'x')",
                     (p,), match="risk_events_chk1")
    savepoint_raises(db, "INSERT INTO risk_events (product_id, event_type, severity, title) VALUES (%s, 'price_drop', 'info', 'x')",
                     (p,), match="risk_events_chk1")


def test_fanout_is_idempotent_and_respects_preferences(db):
    p, r = make_product(db), make_recall(db)
    holder, muted, stranger = make_user(db), make_user(db), make_user(db)
    _hold(db, holder, p)
    w = _hold(db, muted, p)
    db.execute("UPDATE wallet_items SET alerts_enabled = false WHERE id = %s", (w,))
    ev = _recall_event(db, p, r)
    assert one(db, "SELECT telcron_fanout_risk_event(%s)", (ev,)) == 1
    assert one(db, "SELECT telcron_fanout_risk_event(%s)", (ev,)) == 0             # nightly re-run: no new alerts
    assert one(db, "SELECT user_id FROM user_risk_alerts WHERE risk_event_id = %s", (ev,)) == holder


def test_regional_recalls_reach_only_that_region(db):
    p, r = make_product(db), make_recall(db)
    db.execute("INSERT INTO recall_regions (recall_id, country_code, subdivision_code) VALUES (%s, 'US', 'US-CA')", (r,))
    ca, ny, uk, unknown = (make_user(db, country="US", subdivision="US-CA"), make_user(db, country="US", subdivision="US-NY"),
                           make_user(db, country="GB"), make_user(db, country=None))
    for u in (ca, ny, uk, unknown):
        _hold(db, u, p)
    ev = _recall_event(db, p, r)
    db.execute("SELECT telcron_fanout_risk_event(%s)", (ev,))
    alerted = {row[0] for row in db.execute("SELECT user_id FROM user_risk_alerts WHERE risk_event_id = %s", (ev,))}
    assert alerted == {ca, unknown}


def test_timeline_status_flow(db):
    p, r, u = make_product(db), make_recall(db), make_user(db)
    _hold(db, u, p)
    ev = _recall_event(db, p, r)
    db.execute("SELECT telcron_fanout_risk_event(%s)", (ev,))
    a = one(db, "SELECT id FROM user_risk_alerts WHERE user_id = %s", (u,))
    savepoint_raises(db, "UPDATE user_risk_alerts SET status = 'dismissed' WHERE id = %s", (a,), match="user_risk_alerts_chk1")
    db.execute("UPDATE user_risk_alerts SET status = 'dismissed', resolved_at = now() WHERE id = %s", (a,))
    db.execute("INSERT INTO comments (risk_event_id, author_user_id, body) VALUES (%s, %s, 'Mine is affected too')", (ev, u))


def test_feed_items_typed_and_deduplicated(db):
    u, r = make_user(db), make_recall(db)
    savepoint_raises(db, "INSERT INTO feed_items (item_type, data_source_code, published_at) VALUES ('recall', 'cpsc', now())",
                     match="feed_items_chk3")
    db.execute("INSERT INTO feed_items (item_type, data_source_code, recall_id, published_at) VALUES ('recall', 'cpsc', %s, now())", (r,))
    savepoint_raises(db, "INSERT INTO feed_items (item_type, data_source_code, recall_id, published_at) VALUES ('recall', 'cpsc', %s, now())",
                     (r,), match="feed_items_u3_uidx")
    sr = one(db, "INSERT INTO source_records (data_source_code, record_type, external_id, payload, payload_sha256) VALUES ('bestbuy', 'product_listing', 'SKU1', '{}', 'h') RETURNING id")
    db.execute("INSERT INTO feed_items (item_type, data_source_code, external_id, source_record_id, published_at) VALUES ('listing', 'bestbuy', 'SKU1', %s, now())", (sr,))
    savepoint_raises(db, "INSERT INTO feed_items (item_type, data_source_code, external_id, source_record_id, published_at) VALUES ('listing', 'bestbuy', 'SKU1', %s, now())",
                     (sr,), match="feed_items_u1_uidx")
    upload = make_asset(db, u)
    fi = one(db, "INSERT INTO feed_items (item_type, data_source_code, media_asset_id, published_at, country_code) VALUES ('user_upload', 'user_upload', %s, now(), 'US') RETURNING id", (upload,))
    db.execute("INSERT INTO feed_item_topics (feed_item_id, topic_code, confidence) VALUES (%s, 'recalls', 0.9)", (fi,))
    hits = one(db, """SELECT count(*) FROM feed_items f JOIN feed_item_topics t ON t.feed_item_id = f.id
                      WHERE f.country_code = 'US' AND t.topic_code = 'recalls' AND f.data_source_code = 'user_upload'""")
    assert hits == 1


def test_price_alert_one_active_per_wallet_item(db):
    u, p = make_user(db), make_product(db)
    w = _hold(db, u, p)
    db.execute("INSERT INTO price_alerts (wallet_item_id, target_price, currency) VALUES (%s, 49.99, 'USD')", (w,))
    savepoint_raises(db, "INSERT INTO price_alerts (wallet_item_id, target_price, currency) VALUES (%s, 39.99, 'USD')", (w,),
                     match="price_alerts_u1_uidx")
    savepoint_raises(db, "INSERT INTO price_snapshots (product_id, data_source_code, country_code, currency, price, observed_at) VALUES (%s, 'amazon', 'US', 'usd', 10, now())",
                     (p,), match="price_snapshots_chk2")


def test_entitlement_sources(db):
    u = make_user(db)
    savepoint_raises(db, "INSERT INTO user_entitlements (user_id, source, entitlement) VALUES (%s, 'redemption', 'rate_limit_x3')", (u,),
                     match="user_entitlements_chk1")
    db.execute("INSERT INTO user_entitlements (user_id, source, entitlement) VALUES (%s, 'level_perk', 'feature:early_access')", (u,))
