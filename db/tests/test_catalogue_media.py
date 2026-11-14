"""Product registry, dedupe, merges and media (FR-04/05, TC-P1-003/006/008)."""
from conftest import make_asset, make_blob, make_product, make_user, one, savepoint_raises, uid

GTIN = "00012345678905"


def test_one_product_per_barcode(db):
    a, b = make_product(db), make_product(db)
    db.execute("INSERT INTO product_aliases (product_id, alias_type, alias_value) VALUES (%s, 'gtin', %s)", (a, GTIN))
    savepoint_raises(db, "INSERT INTO product_aliases (product_id, alias_type, alias_value) VALUES (%s, 'gtin', %s)",
                     (b, GTIN), match="product_aliases_alias_type_namespace_alias_value_key")


def test_marketplace_ids_are_namespaced(db):
    a, b = make_product(db), make_product(db)
    db.execute("INSERT INTO product_aliases (product_id, alias_type, namespace, alias_value) VALUES (%s, 'marketplace_item', 'amazon.us', 'B0001')", (a,))
    db.execute("INSERT INTO product_aliases (product_id, alias_type, namespace, alias_value) VALUES (%s, 'marketplace_item', 'ebay.us', 'B0001')", (b,))
    savepoint_raises(db, "INSERT INTO product_aliases (product_id, alias_type, alias_value) VALUES (%s, 'marketplace_item', 'B0002')",
                     (a,), match="product_aliases_chk1")          # marketplace id needs a namespace
    savepoint_raises(db, "INSERT INTO product_aliases (product_id, alias_type, alias_value) VALUES (%s, 'gtin', '12345')",
                     (a,), match="product_aliases_chk2")          # GTIN must be normalised to 14 digits


def test_brand_model_unique_but_unknown_brand_allowed(db):
    p = make_product(db, brand="Ninja", model="BL-610")
    savepoint_raises(db, """INSERT INTO products (category_id, brand_id, canonical_name, model_number_normalized,
                                                  identification_source, public_slug)
                            SELECT category_id, brand_id, 'dup', 'BL610', 'text', 'dup-slug-1' FROM products WHERE id = %s""",
                     (p,), match="products_u1_uidx")
    make_product(db, model="1000")
    make_product(db, model="1000")   # unknown brand: same model string is NOT assumed to be the same product


def test_merge_moves_everything_users_touch(db):
    src, dst = make_product(db), make_product(db)
    both, only_src = make_user(db), make_user(db)
    db.execute("INSERT INTO product_aliases (product_id, alias_type, alias_value) VALUES (%s, 'gtin', %s)", (src, GTIN))
    db.execute("INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'search', 'active'), (%s, %s, 'search', 'active'), (%s, %s, 'search', 'active')",
               (both, src, both, dst, only_src, src))
    db.execute("INSERT INTO reviews (product_id, author_user_id, rating, body) VALUES (%s, %s, 4, 'x')", (src, only_src))
    db.execute("SELECT telcron_merge_products(%s, %s)", (src, dst))
    assert one(db, "SELECT product_id FROM product_aliases WHERE alias_value = %s", (GTIN,)) == dst
    assert one(db, "SELECT count(*) FROM wallet_items WHERE user_id = %s AND deleted_at IS NULL", (both,)) == 1
    assert one(db, "SELECT product_id FROM wallet_items WHERE user_id = %s", (only_src,)) == dst
    assert one(db, "SELECT count(*) FROM reviews WHERE product_id = %s", (dst,)) == 1
    assert one(db, "SELECT status::text || ':' || (merged_into_product_id = %s) FROM products WHERE id = %s", (dst, src)) == "merged:true"
    assert one(db, "SELECT count(*) FROM audit_log WHERE action = 'product.merged' AND entity_id = %s", (src,)) == 1


def test_no_merge_chains_or_self_merge(db):
    a, b, c = make_product(db), make_product(db), make_product(db)
    db.execute("SELECT telcron_merge_products(%s, %s)", (a, b))
    savepoint_raises(db, "SELECT telcron_merge_products(%s, %s)", (c, a), match="un-merged")
    savepoint_raises(db, "UPDATE products SET status = 'merged', merged_into_product_id = %s WHERE id = %s", (a, c),
                     match="itself merged")
    savepoint_raises(db, "SELECT telcron_merge_products(%s, %s)", (c, c), match="itself")
    db.execute("SELECT telcron_merge_products(%s, %s)", (b, c))             # merging the target repoints old children
    assert one(db, "SELECT merged_into_product_id FROM products WHERE id = %s", (a,)) == c


def test_same_file_shared_by_two_owners(db):
    u1, u2 = make_user(db), make_user(db)
    blob = make_blob(db)
    a1 = make_asset(db, u1, blob)
    a2 = make_asset(db, u2, blob)            # dedupe on content, not on ownership
    assert a1 != a2
    db.execute("UPDATE media_assets SET visibility = 'public' WHERE id = %s", (a1,))
    assert one(db, "SELECT visibility FROM media_assets WHERE id = %s", (a2,)) == "private"
    savepoint_raises(db, "INSERT INTO media_assets (blob_id, owner_user_id) VALUES (%s, %s)", (blob, u1), match="media_assets_u1_uidx")
    savepoint_raises(db, "INSERT INTO media_blobs (sha256, kind, mime_type, byte_size, storage_key_original) SELECT sha256, kind, mime_type, 1, 'k' FROM media_blobs WHERE id = %s",
                     (blob,), match="media_blobs_sha256_key")


def test_near_duplicate_lookup_by_phash_bands(db):
    base = 0x0F0F_00FF_1234_5678
    near = base ^ 0b101          # Hamming distance 2 (bands 0–2 identical)
    far = ~base                  # completely different
    b_near, b_far = make_blob(db, near), make_blob(db, far)
    found = [r[0] for r in db.execute("""
        SELECT id FROM media_blobs m
         WHERE (m.phash_band0 = ((%(h)s >> 48) & 65535) OR m.phash_band1 = ((%(h)s >> 32) & 65535)
             OR m.phash_band2 = ((%(h)s >> 16) & 65535) OR m.phash_band3 = (%(h)s & 65535))
           AND bit_count((m.perceptual_hash # %(h)s)::bit(64)) <= 6""", {"h": base}).fetchall()]
    assert b_near in found and b_far not in found


def test_identification_request_input_rules(db):
    u = make_user(db)
    savepoint_raises(db, "INSERT INTO identification_requests (user_id, input_type) VALUES (%s, 'barcode')", (u,),
                     match="identification_requests_chk1")
    savepoint_raises(db, "INSERT INTO identification_requests (user_id, input_type, text_query, status) VALUES (%s, 'text', 'x', 'identified')",
                     (u,), match="identification_requests_chk5")
    db.execute("INSERT INTO identification_requests (user_id, input_type, barcode_value) VALUES (%s, 'barcode', %s)", (u, GTIN))
