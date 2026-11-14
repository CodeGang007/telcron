"""Identity & access: in-house auth invariants (TC-P1-001/002) and account deletion."""
from conftest import make_user, make_product, one, savepoint_raises, uid


def test_level1_requires_verified_email_and_phone(db):
    savepoint_raises(db, """INSERT INTO users (email, email_verified_at, display_name, referral_code, verification_level)
                            VALUES ('a@x.com', now(), 'A', 'R1', 1)""", match="users_chk3")
    uid_ = make_user(db, level=1)
    assert one(db, "SELECT verification_level FROM users WHERE id = %s", (uid_,)) == 1


def test_google_only_user_has_no_password_and_level0(db):
    u = one(db, """INSERT INTO users (email, email_verified_at, display_name, referral_code)
                   VALUES ('g@x.com', now(), 'G', 'RG') RETURNING id""")
    db.execute("""INSERT INTO user_identities (user_id, provider, provider_subject, provider_email, provider_email_verified)
                  VALUES (%s, 'google', '1093', 'g@x.com', true)""", (u,))
    assert one(db, "SELECT password_hash IS NULL AND verification_level = 0 FROM users WHERE id = %s", (u,))


def test_oauth_subject_maps_to_exactly_one_user(db):
    a, b = make_user(db), make_user(db)
    db.execute("INSERT INTO user_identities (user_id, provider, provider_subject) VALUES (%s, 'google', 'sub-1')", (a,))
    savepoint_raises(db, "INSERT INTO user_identities (user_id, provider, provider_subject) VALUES (%s, 'google', 'sub-1')",
                     (b,), match="user_identities_provider_provider_subject_key")


def test_phone_unique_only_once_verified(db):
    for _ in range(2):   # unverified duplicates allowed (nobody can squat a number)
        db.execute("""INSERT INTO users (email, phone_e164, display_name, referral_code)
                      VALUES (%s, '+15550001111', 'P', %s)""", (f"p{uid()}@x.com", uid()))
    db.execute("""INSERT INTO users (email, phone_e164, phone_verified_at, display_name, referral_code)
                  VALUES (%s, '+15550002222', now(), 'P', %s)""", (f"p{uid()}@x.com", uid()))
    savepoint_raises(db, """INSERT INTO users (email, phone_e164, phone_verified_at, display_name, referral_code)
                            VALUES ('dup@x.com', '+15550002222', now(), 'P', 'RDUP')""", match="users_u1_uidx")


def test_email_is_case_insensitive(db):
    db.execute("INSERT INTO users (email, display_name, referral_code) VALUES ('Case@X.com', 'C', 'RC1')")
    savepoint_raises(db, "INSERT INTO users (email, display_name, referral_code) VALUES ('case@x.COM', 'C', 'RC2')",
                     match="users_email_key")


def test_session_absolute_cap_cannot_slide(db):
    u = make_user(db)
    savepoint_raises(db, """INSERT INTO sessions (user_id, family_id, refresh_token_hash, family_expires_at, expires_at)
                            VALUES (%s, gen_random_uuid(), 'h1', now() + interval '90 min', now() + interval '2 hours')""",
                     (u,), match="sessions_chk1")


def test_session_rotation_links_replacement(db):
    u = make_user(db)
    fam = one(db, "SELECT gen_random_uuid()")
    s1 = one(db, """INSERT INTO sessions (user_id, family_id, refresh_token_hash, family_expires_at, expires_at)
                    VALUES (%s, %s, 't1', now() + interval '90 min', now() + interval '20 min') RETURNING id""", (u, fam))
    s2 = one(db, """INSERT INTO sessions (user_id, family_id, refresh_token_hash, family_expires_at, expires_at)
                    SELECT user_id, family_id, 't2', family_expires_at, least(family_expires_at, now() + interval '20 min')
                    FROM sessions WHERE id = %s RETURNING id""", (s1,))
    db.execute("UPDATE sessions SET rotated_at = now(), replaced_by_session_id = %s WHERE id = %s", (s2, s1))
    savepoint_raises(db, "UPDATE sessions SET rotated_at = now() WHERE id = %s", (s2,), match="sessions_chk2")


def test_verification_token_hash_unique_and_attempts_bounded(db):
    u = make_user(db)
    db.execute("""INSERT INTO verification_tokens (user_id, purpose, target, token_hash, expires_at)
                  VALUES (%s, 'phone_otp', '+15550003333', 'hash-1', now() + interval '10 min')""", (u,))
    savepoint_raises(db, """INSERT INTO verification_tokens (user_id, purpose, target, token_hash, expires_at)
                            VALUES (%s, 'password_reset', 'x', 'hash-1', now() + interval '1 hour')""", (u,),
                     match="verification_tokens_token_hash_key")
    savepoint_raises(db, "UPDATE verification_tokens SET attempt_count = 11 WHERE user_id = %s", (u,),
                     match="verification_tokens_chk1")


def test_auth_events_are_append_only_and_partitioned(db):
    db.execute("INSERT INTO auth_events (event_type, email_attempted, ip_address) VALUES ('login_failed', 'z@x.com', '1.2.3.4')")
    part = one(db, "SELECT tableoid::regclass::text FROM auth_events WHERE email_attempted = 'z@x.com'")
    assert part.startswith("auth_events_20"), part  # landed in a monthly partition, not default
    savepoint_raises(db, "UPDATE auth_events SET failure_reason = 'x' WHERE email_attempted = 'z@x.com'", match="append-only")
    savepoint_raises(db, "DELETE FROM auth_events WHERE email_attempted = 'z@x.com'", match="append-only")


def test_account_anonymisation(db):
    u = make_user(db)
    p = make_product(db)
    db.execute("INSERT INTO user_identities (user_id, provider, provider_subject) VALUES (%s, 'google', %s)", (u, uid()))
    db.execute("""INSERT INTO sessions (user_id, family_id, refresh_token_hash, family_expires_at, expires_at)
                  VALUES (%s, gen_random_uuid(), %s, now() + interval '1 h', now() + interval '20 min')""", (u, uid()))
    db.execute("INSERT INTO auth_events (user_id, event_type, email_attempted, ip_address) VALUES (%s, 'login_succeeded', 'me@x.com', '9.9.9.9')", (u,))
    db.execute("INSERT INTO wallet_items (user_id, product_id, add_method, status) VALUES (%s, %s, 'search', 'active')", (u, p))
    rid = one(db, "INSERT INTO reviews (product_id, author_user_id, rating, body) VALUES (%s, %s, 5, 'ok') RETURNING id", (p, u))
    db.execute("SELECT telcron_anonymise_user(%s)", (u,))
    row = db.execute("SELECT email, phone_e164, password_hash, status, display_name FROM users WHERE id = %s", (u,)).fetchone()
    assert row[0].startswith("deleted+") and row[1] is None and row[2] is None and row[3] == "deleted"
    assert one(db, "SELECT count(*) FROM user_identities WHERE user_id = %s", (u,)) == 0   # Google account can re-register
    assert one(db, "SELECT count(*) FROM sessions WHERE user_id = %s", (u,)) == 0
    assert one(db, "SELECT count(*) FROM wallet_items WHERE user_id = %s", (u,)) == 0
    assert one(db, "SELECT email_attempted IS NULL AND ip_address IS NULL FROM auth_events WHERE user_id = %s", (u,))
    assert one(db, "SELECT count(*) FROM reviews WHERE id = %s", (rid,)) == 1             # public contribution kept
    assert one(db, "SELECT current_setting('telcron.allow_purge', true)") == "off"       # purge flag closed again
