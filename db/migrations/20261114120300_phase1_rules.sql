-- Core business rules that cannot be expressed as declarative constraints. Hand-written.
-- Every rule here is covered by db/tests.

-- migrate:up

-- ─────────────── Catalogue: merges ───────────────

-- A product may only be merged into an ACTIVE (non-merged) product — no merge chains.
CREATE OR REPLACE FUNCTION telcron_products_merge_target_check() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.merged_into_product_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM products WHERE id = NEW.merged_into_product_id AND status = 'merged') THEN
        RAISE EXCEPTION 'telcron: cannot merge into product % which is itself merged', NEW.merged_into_product_id
            USING ERRCODE = 'TC002';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER products_merge_target_check BEFORE INSERT OR UPDATE OF merged_into_product_id ON products
    FOR EACH ROW EXECUTE FUNCTION telcron_products_merge_target_check();

-- Merge duplicate product p_src into canonical p_dst. History (screenings, passports, checks) stays
-- with p_src; everything users and lookups touch moves to p_dst. Later-phase tables are moved when present.
CREATE OR REPLACE FUNCTION telcron_merge_products(p_src uuid, p_dst uuid, p_actor uuid DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    t text;
BEGIN
    IF p_src = p_dst THEN
        RAISE EXCEPTION 'telcron: cannot merge a product into itself' USING ERRCODE = 'TC002';
    END IF;
    PERFORM 1 FROM products WHERE id IN (p_src, p_dst) AND status <> 'merged' FOR UPDATE;
    IF NOT FOUND OR (SELECT count(*) FROM products WHERE id IN (p_src, p_dst) AND status <> 'merged') <> 2 THEN
        RAISE EXCEPTION 'telcron: both products must exist and be un-merged' USING ERRCODE = 'TC002';
    END IF;

    UPDATE product_aliases SET product_id = p_dst WHERE product_id = p_src;

    INSERT INTO product_media (product_id, media_asset_id, role, sort_order)
    SELECT p_dst, media_asset_id, 'gallery', sort_order FROM product_media WHERE product_id = p_src
    ON CONFLICT DO NOTHING;
    DELETE FROM product_media WHERE product_id = p_src;

    -- users holding both: drop the duplicate entry; others: repoint (passport pointer belongs to src → reset)
    UPDATE wallet_items w SET deleted_at = now()
     WHERE w.product_id = p_src AND w.deleted_at IS NULL
       AND EXISTS (SELECT 1 FROM wallet_items d WHERE d.user_id = w.user_id AND d.product_id = p_dst AND d.deleted_at IS NULL);
    UPDATE wallet_items SET product_id = p_dst, last_seen_passport_id = NULL WHERE product_id = p_src;

    UPDATE reviews SET product_id = p_dst WHERE product_id = p_src;

    UPDATE product_certifications c SET product_id = p_dst
     WHERE c.product_id = p_src
       AND NOT EXISTS (SELECT 1 FROM product_certifications d WHERE d.product_id = p_dst
                        AND d.scheme_code = c.scheme_code AND d.certificate_identifier = c.certificate_identifier);

    FOREACH t IN ARRAY ARRAY['posts', 'hazard_flags', 'product_fact_reports', 'price_snapshots', 'feed_items',
                             'media_annotations', 'product_traceability', 'product_variants'] LOOP
        IF to_regclass(t) IS NOT NULL THEN
            EXECUTE format('UPDATE %I SET product_id = $1 WHERE product_id = $2', t) USING p_dst, p_src;
        END IF;
    END LOOP;
    IF to_regclass('product_watches') IS NOT NULL THEN
        DELETE FROM product_watches w WHERE w.product_id = p_src
           AND EXISTS (SELECT 1 FROM product_watches d WHERE d.user_id = w.user_id AND d.product_id = p_dst);
        UPDATE product_watches SET product_id = p_dst WHERE product_id = p_src;
    END IF;

    UPDATE products SET merged_into_product_id = p_dst WHERE merged_into_product_id = p_src;
    UPDATE products SET status = 'merged', merged_into_product_id = p_dst WHERE id = p_src;

    INSERT INTO audit_log (actor_type, actor_user_id, action, entity_type, entity_id, changes)
    VALUES (CASE WHEN p_actor IS NULL THEN 'system' ELSE 'admin' END::actor_type, p_actor, 'product.merged', 'product', p_src,
            jsonb_build_object('merged_into', p_dst));
END $$;

-- ─────────────── Certifications: keep the "current status" cache in sync ───────────────
CREATE OR REPLACE FUNCTION telcron_certification_checks_sync() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE product_certifications
       SET current_status = NEW.status, last_check_id = NEW.id
     WHERE id = NEW.product_certification_id;
    RETURN NEW;
END $$;
CREATE TRIGGER certification_checks_sync AFTER INSERT ON certification_checks
    FOR EACH ROW EXECUTE FUNCTION telcron_certification_checks_sync();

-- ─────────────── Screening ───────────────

-- A screening completes exactly once (running → completed | failed).
CREATE OR REPLACE FUNCTION telcron_screenings_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status <> 'running' THEN
        RAISE EXCEPTION 'telcron: screening % is % and can no longer change', OLD.id, OLD.status
            USING ERRCODE = 'TC003';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER screenings_transition BEFORE UPDATE ON screenings
    FOR EACH ROW EXECUTE FUNCTION telcron_screenings_transition();

-- Deferred: a match / near_match verdict must be backed by at least one candidate with that verdict.
CREATE OR REPLACE FUNCTION telcron_screenings_verdict_cited() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.verdict IN ('match', 'near_match') AND NOT EXISTS (
        SELECT 1 FROM screening_matches m
         WHERE m.screening_id = NEW.id AND m.verdict::text = NEW.verdict::text) THEN
        RAISE EXCEPTION 'telcron: screening % has verdict % but cites no % candidate', NEW.id, NEW.verdict, NEW.verdict
            USING ERRCODE = 'TC004';
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER screenings_verdict_cited AFTER INSERT OR UPDATE ON screenings
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION telcron_screenings_verdict_cited();

-- ─────────────── Passports ───────────────

-- Version sequencing + badge semantics; then point the product at its new current passport.
CREATE OR REPLACE FUNCTION telcron_passports_before_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    expected int;
    s record;
BEGIN
    PERFORM 1 FROM products WHERE id = NEW.product_id FOR UPDATE;   -- serialise versioning per product
    SELECT coalesce(max(version), 0) + 1 INTO expected FROM passports WHERE product_id = NEW.product_id;
    IF NEW.version IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'telcron: passport version must be % for product %, got %', expected, NEW.product_id, NEW.version
            USING ERRCODE = 'TC005';
    END IF;

    IF NEW.screening_id IS NULL THEN
        IF NEW.status_badge = 'recalled' THEN
            RAISE EXCEPTION 'telcron: badge "recalled" requires a match/near_match screening' USING ERRCODE = 'TC005';
        END IF;
        RETURN NEW;
    END IF;

    SELECT status, verdict INTO s FROM screenings WHERE id = NEW.screening_id;
    IF s.status <> 'completed' THEN
        RAISE EXCEPTION 'telcron: passport cites screening % which is not completed', NEW.screening_id
            USING ERRCODE = 'TC005';
    END IF;
    IF s.verdict = 'match' AND NEW.status_badge <> 'recalled' THEN
        RAISE EXCEPTION 'telcron: recall match requires badge "recalled"' USING ERRCODE = 'TC005';
    END IF;
    IF NEW.status_badge = 'recalled' AND s.verdict NOT IN ('match', 'near_match') THEN
        RAISE EXCEPTION 'telcron: badge "recalled" requires a match/near_match screening' USING ERRCODE = 'TC005';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER passports_before_insert BEFORE INSERT ON passports
    FOR EACH ROW EXECUTE FUNCTION telcron_passports_before_insert();

CREATE OR REPLACE FUNCTION telcron_passports_after_insert() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE products SET current_passport_id = NEW.id WHERE id = NEW.product_id;
    RETURN NEW;
END $$;
CREATE TRIGGER passports_after_insert AFTER INSERT ON passports
    FOR EACH ROW EXECUTE FUNCTION telcron_passports_after_insert();

-- ─────────────── Wallet ───────────────

-- The verification that activates a manual/barcode add must be a successful match.
CREATE OR REPLACE FUNCTION telcron_wallet_items_verification_check() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.verified_by_verification_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM wallet_item_verifications WHERE id = NEW.verified_by_verification_id AND result = 'matched') THEN
        RAISE EXCEPTION 'telcron: wallet item % references a verification that is not "matched"', NEW.id
            USING ERRCODE = 'TC006';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER wallet_items_verification_check BEFORE INSERT OR UPDATE OF verified_by_verification_id ON wallet_items
    FOR EACH ROW EXECUTE FUNCTION telcron_wallet_items_verification_check();

-- A label can only be attached to a wallet item of the same user.
CREATE OR REPLACE FUNCTION telcron_wallet_item_labels_owner_check() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT user_id FROM wallet_items WHERE id = NEW.wallet_item_id)
       IS DISTINCT FROM (SELECT user_id FROM wallet_labels WHERE id = NEW.label_id) THEN
        RAISE EXCEPTION 'telcron: label and wallet item belong to different users' USING ERRCODE = 'TC006';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER wallet_item_labels_owner_check BEFORE INSERT OR UPDATE ON wallet_item_labels
    FOR EACH ROW EXECUTE FUNCTION telcron_wallet_item_labels_owner_check();

-- ─────────────── Reviews: helpful_count cache ───────────────
CREATE OR REPLACE FUNCTION telcron_review_votes_count() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE reviews SET helpful_count = helpful_count + 1 WHERE id = NEW.review_id;
    ELSE
        UPDATE reviews SET helpful_count = helpful_count - 1 WHERE id = OLD.review_id;
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER review_votes_count AFTER INSERT OR DELETE ON review_votes
    FOR EACH ROW EXECUTE FUNCTION telcron_review_votes_count();

-- ─────────────── Account deletion (privacy) ───────────────
-- Anonymises the person, removes credentials and private data; keeps shared product knowledge
-- and the user's public contributions (shown as "Deleted user").
CREATE OR REPLACE FUNCTION telcron_anonymise_user(p_user uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    t text;
BEGIN
    PERFORM set_config('telcron.allow_purge', 'on', true);

    DELETE FROM user_identities     WHERE user_id = p_user;
    DELETE FROM sessions            WHERE user_id = p_user;
    DELETE FROM verification_tokens WHERE user_id = p_user;
    DELETE FROM wallet_items        WHERE user_id = p_user;
    DELETE FROM wallet_labels       WHERE user_id = p_user;
    UPDATE media_assets SET deleted_at = coalesce(deleted_at, now()), visibility = 'private'
     WHERE owner_user_id = p_user;
    UPDATE auth_events SET email_attempted = NULL, ip_address = NULL, user_agent = NULL WHERE user_id = p_user;
    UPDATE audit_log   SET ip_address = NULL WHERE actor_user_id = p_user;

    FOREACH t IN ARRAY ARRAY['search_queries', 'notifications', 'notification_preferences', 'user_devices',
                             'product_watches', 'user_daily_logins'] LOOP
        IF to_regclass(t) IS NOT NULL THEN
            EXECUTE format('DELETE FROM %I WHERE user_id = $1', t) USING p_user;
        END IF;
    END LOOP;
    IF to_regclass('feed_interactions') IS NOT NULL THEN
        DELETE FROM feed_interactions WHERE user_id = p_user;
    END IF;
    IF to_regclass('posts') IS NOT NULL THEN
        UPDATE posts SET geohash = NULL, location_name = NULL WHERE author_user_id = p_user;
    END IF;

    UPDATE users SET email = 'deleted+' || id || '@invalid.telcron', email_verified_at = NULL,
                     phone_e164 = NULL, phone_verified_at = NULL, password_hash = NULL,
                     display_name = 'Deleted user', avatar_media_id = NULL, subdivision_code = NULL,
                     verification_level = 0, status = 'deleted', deleted_at = now(), locked_until = NULL
     WHERE id = p_user;

    INSERT INTO audit_log (actor_type, actor_user_id, action, entity_type, entity_id)
    VALUES ('system', NULL, 'user.anonymised', 'user', p_user);
    PERFORM set_config('telcron.allow_purge', 'off', true);
END $$;

-- migrate:down
DROP FUNCTION IF EXISTS telcron_anonymise_user(uuid);
DROP TRIGGER IF EXISTS review_votes_count ON review_votes;
DROP FUNCTION IF EXISTS telcron_review_votes_count();
DROP TRIGGER IF EXISTS wallet_item_labels_owner_check ON wallet_item_labels;
DROP FUNCTION IF EXISTS telcron_wallet_item_labels_owner_check();
DROP TRIGGER IF EXISTS wallet_items_verification_check ON wallet_items;
DROP FUNCTION IF EXISTS telcron_wallet_items_verification_check();
DROP TRIGGER IF EXISTS passports_after_insert ON passports;
DROP FUNCTION IF EXISTS telcron_passports_after_insert();
DROP TRIGGER IF EXISTS passports_before_insert ON passports;
DROP FUNCTION IF EXISTS telcron_passports_before_insert();
DROP TRIGGER IF EXISTS screenings_verdict_cited ON screenings;
DROP FUNCTION IF EXISTS telcron_screenings_verdict_cited();
DROP TRIGGER IF EXISTS screenings_transition ON screenings;
DROP FUNCTION IF EXISTS telcron_screenings_transition();
DROP TRIGGER IF EXISTS certification_checks_sync ON certification_checks;
DROP FUNCTION IF EXISTS telcron_certification_checks_sync();
DROP FUNCTION IF EXISTS telcron_merge_products(uuid, uuid, uuid);
DROP TRIGGER IF EXISTS products_merge_target_check ON products;
DROP FUNCTION IF EXISTS telcron_products_merge_target_check();
