"""Wallet (TC-P1-013/014), reviews and community (TC-P1-021…025)."""
from conftest import make_asset, make_product, make_user, one, savepoint_raises, uid


def test_manual_add_stays_pending_until_matched_video(db):
    u, p = make_user(db), make_product(db)
    savepoint_raises(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'manual', 'active')",
                     (u, p), match="wallet_items_chk1")
    w = one(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'manual', 'pending_verification') RETURNING id", (u, p))
    video = make_asset(db, u)
    bad = one(db, "INSERT INTO wallet_item_verifications (wallet_item_id, media_asset_id, result, mismatch_reason) VALUES (%s, %s, 'mismatch', 'different model') RETURNING id", (w, video))
    savepoint_raises(db, "UPDATE wallet_items SET verified_by_verification_id = %s, status = 'active' WHERE id = %s", (bad, w),
                     match="not \"matched\"")
    ok = one(db, "INSERT INTO wallet_item_verifications (wallet_item_id, media_asset_id, result, confidence) VALUES (%s, %s, 'matched', 0.93) RETURNING id", (w, video))
    db.execute("UPDATE wallet_items SET verified_by_verification_id = %s, status = 'active' WHERE id = %s", (ok, w))
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_verification_must_belong_to_the_same_wallet_item(db):
    u, p1, p2 = make_user(db), make_product(db), make_product(db)
    w1 = one(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'barcode', 'pending_verification') RETURNING id", (u, p1))
    w2 = one(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'barcode', 'pending_verification') RETURNING id", (u, p2))
    v2 = one(db, "INSERT INTO wallet_item_verifications (wallet_item_id, media_asset_id, result) VALUES (%s, %s, 'matched') RETURNING id", (w2, make_asset(db, u)))
    savepoint_raises(db, "UPDATE wallet_items SET verified_by_verification_id = %s, status = 'active' WHERE id = %s", (v2, w1),
                     match="wallet_items_verified_by_verification_id_id_fkey")


def test_media_grid_add_needs_no_video(db):
    u, p = make_user(db), make_product(db)
    db.execute("INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'media_grid', 'active')", (u, p))


def test_one_active_wallet_entry_per_product_and_readd_after_delete(db):
    u, p = make_user(db), make_product(db)
    w = one(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'search', 'active') RETURNING id", (u, p))
    savepoint_raises(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'search', 'active')",
                     (u, p), match="wallet_items_u1_uidx")
    db.execute("UPDATE wallet_items SET deleted_at = now() WHERE id = %s", (w,))
    db.execute("INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'search', 'active')", (u, p))


def test_labels_are_per_user_case_insensitive_and_owner_checked(db):
    a, b, p = make_user(db), make_user(db), make_product(db)
    la = one(db, "INSERT INTO wallet_labels (user_id, name) VALUES (%s, 'Kitchen') RETURNING id", (a,))
    savepoint_raises(db, "INSERT INTO wallet_labels (user_id, name) VALUES (%s, 'kitchen')", (a,), match="wallet_labels_u1_uidx")
    db.execute("INSERT INTO wallet_labels (user_id, name) VALUES (%s, 'kitchen')", (b,))
    wb = one(db, "INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'search', 'active') RETURNING id", (b, p))
    savepoint_raises(db, "INSERT INTO wallet_item_labels (wallet_item_id, label_id) VALUES (%s, %s)", (wb, la), match="different users")


def test_reviews_votes_and_counts(db):
    a, b, p = make_user(db), make_user(db), make_product(db)
    savepoint_raises(db, "INSERT INTO reviews (product_id, author_user_id, rating, body) VALUES (%s, %s, 6, 'x')", (p, a), match="reviews_chk1")
    r = one(db, "INSERT INTO reviews (product_id, author_user_id, rating, title, body) VALUES (%s, %s, 4, 'Good', 'Works') RETURNING id", (p, a))
    db.execute("INSERT INTO review_votes (review_id, user_id) VALUES (%s, %s)", (r, b))
    savepoint_raises(db, "INSERT INTO review_votes (review_id, user_id) VALUES (%s, %s)", (r, b), match="review_votes_pkey")
    assert one(db, "SELECT helpful_count FROM reviews WHERE id = %s", (r,)) == 1
    db.execute("DELETE FROM review_votes WHERE review_id = %s", (r,))
    assert one(db, "SELECT helpful_count FROM reviews WHERE id = %s", (r,)) == 0


def test_ingested_reviews_are_keyed_on_source(db):
    p = make_product(db)
    sr = one(db, "INSERT INTO source_records (data_source_code, record_type, external_id, payload, payload_sha256) VALUES ('amazon', 'review', 'R1', '{}', 'h') RETURNING id")
    db.execute("""INSERT INTO reviews (product_id, origin, data_source_code, external_id, source_record_id, rating, body)
                  VALUES (%s, 'ingested', 'amazon', 'R1', %s, 2, 'leaks')""", (p, sr))
    savepoint_raises(db, """INSERT INTO reviews (product_id, origin, data_source_code, external_id, source_record_id, rating, body)
                            VALUES (%s, 'ingested', 'amazon', 'R1', %s, 2, 'leaks')""", (p, sr), match="reviews_u1_uidx")
    savepoint_raises(db, "INSERT INTO reviews (product_id, origin, rating, body) VALUES (%s, 'ingested', 3, 'no source')", (p,),
                     match="reviews_chk")


def test_posts_store_only_coarse_location(db):
    u, p = make_user(db), make_product(db)
    savepoint_raises(db, "INSERT INTO posts (author_user_id, product_id, body, geohash) VALUES (%s, %s, 'x', 'dr5ru7k2')", (u, p),
                     match="posts_chk1")       # precision 8 (~20 m) rejected
    post = one(db, "INSERT INTO posts (author_user_id, product_id, body, geohash) VALUES (%s, %s, 'x', 'dr5ru7') RETURNING id", (u, p))
    near = [r[0] for r in db.execute("SELECT id FROM posts WHERE geohash LIKE 'dr5r%'").fetchall()]
    assert post in near


def test_comments_target_exactly_one_thread_and_counters(db):
    u, p = make_user(db), make_product(db)
    post = one(db, "INSERT INTO posts (author_user_id, product_id, body) VALUES (%s, %s, 'x') RETURNING id", (u, p))
    savepoint_raises(db, "INSERT INTO comments (author_user_id, body) VALUES (%s, 'orphan')", (u,), match="comments_chk1")
    c = one(db, "INSERT INTO comments (post_id, author_user_id, body) VALUES (%s, %s, 'hi') RETURNING id", (post, u))
    db.execute("INSERT INTO comments (post_id, author_user_id, parent_comment_id, body) VALUES (%s, %s, %s, 'reply')", (post, u, c))
    db.execute("INSERT INTO reactions (post_id, user_id, reaction) VALUES (%s, %s, 'helpful')", (post, u))
    assert db.execute("SELECT comment_count, reaction_count FROM posts WHERE id = %s", (post,)).fetchone() == (2, 1)


def test_community_feed_view_unions_sources(db):
    u, p = make_user(db), make_product(db)
    db.execute("INSERT INTO posts (author_user_id, product_id, body) VALUES (%s, %s, 'post')", (u, p))
    db.execute("INSERT INTO reviews (product_id, author_user_id, rating, body) VALUES (%s, %s, 3, 'review')", (p, u))
    db.execute("INSERT INTO hazard_flags (reporter_user_id, product_id, dimension_code, description) VALUES (%s, %s, 'safety.health_safety', 'sharp edge')", (u, p))
    kinds = {r[0] for r in db.execute("SELECT kind FROM community_feed WHERE product_id = %s", (p,)).fetchall()}
    assert kinds == {"post", "review", "hazard_flag"}
