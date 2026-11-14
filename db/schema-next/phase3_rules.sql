-- Phase 3 (engagement) rules. Hand-written; apply after phase3_schema.sql.
-- TelCoin writes MUST go through the coin_* functions: they serialise per user on the
-- coin_balances row, which makes caps, limits and balances race-free.

-- ─────────────── Ledger status machine ───────────────
CREATE OR REPLACE FUNCTION telcron_ledger_transition() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NOT ((OLD.status = 'pending' AND NEW.status IN ('confirmed', 'frozen', 'reversed'))
             OR (OLD.status = 'frozen'  AND NEW.status IN ('confirmed', 'reversed'))) THEN
            RAISE EXCEPTION 'telcron: ledger entry % cannot move % → %', OLD.id, OLD.status, NEW.status
                USING ERRCODE = 'TC009';
        END IF;
        NEW.status_changed_at := now();
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER coin_ledger_entries_transition BEFORE UPDATE ON coin_ledger_entries
    FOR EACH ROW EXECUTE FUNCTION telcron_ledger_transition();

-- Locks (creating if needed) the user's balance row. Every coin_* function calls this first.
CREATE OR REPLACE FUNCTION coin_lock_balance(p_user uuid) RETURNS coin_balances
LANGUAGE plpgsql AS $$
DECLARE
    b coin_balances;
BEGIN
    INSERT INTO coin_balances (user_id) VALUES (p_user) ON CONFLICT (user_id) DO NOTHING;
    SELECT * INTO b FROM coin_balances WHERE user_id = p_user FOR UPDATE;
    RETURN b;
END $$;

-- Freeze all pending coins of the hold's user.
CREATE OR REPLACE FUNCTION coin_apply_hold(p_hold uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_user uuid;
    s bigint;
BEGIN
    SELECT user_id INTO STRICT v_user FROM fraud_holds WHERE id = p_hold AND status = 'open';
    PERFORM coin_lock_balance(v_user);
    WITH f AS (
        UPDATE coin_ledger_entries SET status = 'frozen', fraud_hold_id = p_hold
         WHERE user_id = v_user AND status = 'pending' RETURNING amount)
    SELECT coalesce(sum(amount), 0) INTO s FROM f;
    UPDATE coin_balances SET pending_balance = pending_balance - s, frozen_balance = frozen_balance + s
     WHERE user_id = v_user;
END $$;

-- Resolve a hold: fraud ⇒ frozen coins reversed; otherwise released and confirmed.
CREATE OR REPLACE FUNCTION coin_resolve_hold(p_hold uuid, p_is_fraud boolean, p_actor uuid) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    v_user uuid;
    s bigint;
BEGIN
    SELECT user_id INTO STRICT v_user FROM fraud_holds WHERE id = p_hold AND status = 'open';
    PERFORM coin_lock_balance(v_user);
    WITH f AS (
        UPDATE coin_ledger_entries
           SET status = CASE WHEN p_is_fraud THEN 'reversed' ELSE 'confirmed' END::ledger_status
         WHERE fraud_hold_id = p_hold AND status = 'frozen' RETURNING amount)
    SELECT coalesce(sum(amount), 0) INTO s FROM f;
    UPDATE coin_balances
       SET frozen_balance    = frozen_balance - s,
           confirmed_balance = confirmed_balance + CASE WHEN p_is_fraud THEN 0 ELSE s END,
           lifetime_earned   = lifetime_earned   + CASE WHEN p_is_fraud THEN 0 ELSE s END
     WHERE user_id = v_user;
    UPDATE fraud_holds
       SET status = CASE WHEN p_is_fraud THEN 'confirmed_fraud' ELSE 'released' END::hold_status,
           resolved_by_user_id = p_actor, resolved_at = now()
     WHERE id = p_hold;
END $$;

-- Award coins for a rule. Idempotent on p_idempotency_key. Returns the earn entry id, or NULL when
-- nothing is awarded (limit reached / daily cap exhausted). Applies the reward-level bonus.
CREATE OR REPLACE FUNCTION coin_earn(p_user uuid, p_rule text, p_idempotency_key text,
                                     p_subject_type text DEFAULT NULL, p_subject_id uuid DEFAULT NULL,
                                     p_reference_type text DEFAULT NULL, p_reference_id uuid DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    b coin_balances;
    r coin_earn_rules;
    v_existing uuid;
    v_awarded bigint;
    v_today bigint;
    v_hold uuid;
    v_status ledger_status;
    v_entry uuid;
    v_pct numeric;
    v_bonus bigint := 0;
BEGIN
    b := coin_lock_balance(p_user);

    SELECT id INTO v_existing FROM coin_ledger_entries WHERE idempotency_key = p_idempotency_key;
    IF FOUND THEN RETURN v_existing; END IF;

    SELECT * INTO r FROM coin_earn_rules WHERE code = p_rule AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'telcron: unknown or inactive earn rule %', p_rule USING ERRCODE = 'TC010';
    END IF;

    IF r.lifetime_limit IS NOT NULL AND (
        SELECT count(*) FROM coin_ledger_entries
         WHERE user_id = p_user AND rule_code = p_rule AND entry_type = 'earn' AND status <> 'reversed'
    ) >= r.lifetime_limit THEN
        RETURN NULL;
    END IF;

    IF r.per_subject_limit IS NOT NULL THEN
        IF p_subject_id IS NULL THEN
            RAISE EXCEPTION 'telcron: rule % needs a subject', p_rule USING ERRCODE = 'TC010';
        END IF;
        IF (SELECT count(*) FROM coin_ledger_entries
             WHERE user_id = p_user AND rule_code = p_rule AND subject_id = p_subject_id
               AND entry_type = 'earn' AND status <> 'reversed') >= r.per_subject_limit THEN
            RETURN NULL;
        END IF;
    END IF;

    v_awarded := r.amount;
    IF r.counts_toward_daily_cap THEN
        SELECT coalesce(sum(e.amount), 0) INTO v_today
          FROM coin_ledger_entries e JOIN coin_earn_rules rr ON rr.code = e.rule_code
         WHERE e.user_id = p_user AND e.entry_type = 'earn' AND e.status <> 'reversed'
           AND rr.counts_toward_daily_cap AND e.created_at >= date_trunc('day', now());
        v_awarded := least(v_awarded, telcron_setting_int('rewards.daily_cap', 500) - v_today);
        IF v_awarded <= 0 THEN RETURN NULL; END IF;
    END IF;

    SELECT id INTO v_hold FROM fraud_holds WHERE user_id = p_user AND status = 'open' LIMIT 1;
    IF v_hold IS NULL AND (
        SELECT count(*) FROM coin_ledger_entries
         WHERE user_id = p_user AND entry_type = 'earn' AND created_at > now() - interval '5 minutes'
    ) >= telcron_setting_int('rewards.rapid_fire_threshold', 20) THEN
        INSERT INTO fraud_holds (user_id, reason, rule_triggered)
        VALUES (p_user, 'Unusually many rewarded actions in 5 minutes', 'rapid_fire') RETURNING id INTO v_hold;
        PERFORM coin_apply_hold(v_hold);
    END IF;
    v_status := CASE WHEN v_hold IS NULL THEN 'pending' ELSE 'frozen' END;

    INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, rule_code, subject_type, subject_id,
                                     reference_type, reference_id, fraud_hold_id, idempotency_key, confirmable_at)
    VALUES (p_user, 'earn', v_awarded, v_status, p_rule, p_subject_type, p_subject_id,
            p_reference_type, p_reference_id, v_hold, p_idempotency_key, now() + r.confirmation_delay)
    RETURNING id INTO v_entry;

    SELECT earn_bonus_pct INTO v_pct FROM reward_levels
     WHERE min_lifetime_coins <= b.lifetime_earned ORDER BY min_lifetime_coins DESC LIMIT 1;
    v_bonus := floor(v_awarded * coalesce(v_pct, 0) / 100);
    IF v_bonus > 0 THEN
        INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, reference_type, reference_id,
                                         fraud_hold_id, idempotency_key, confirmable_at)
        VALUES (p_user, 'level_bonus', v_bonus, v_status, 'ledger_entry', v_entry, v_hold,
                p_idempotency_key || ':bonus', now() + r.confirmation_delay);
    END IF;

    IF v_status = 'pending' THEN
        UPDATE coin_balances SET pending_balance = pending_balance + v_awarded + v_bonus WHERE user_id = p_user;
    ELSE
        UPDATE coin_balances SET frozen_balance = frozen_balance + v_awarded + v_bonus WHERE user_id = p_user;
    END IF;
    RETURN v_entry;
END $$;

-- Confirm every pending entry whose fraud-review window has passed. Returns entries confirmed.
CREATE OR REPLACE FUNCTION coin_confirm_due() RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    v_user uuid;
    s bigint;
    n integer;
    total integer := 0;
BEGIN
    FOR v_user IN SELECT DISTINCT user_id FROM coin_ledger_entries
                   WHERE status = 'pending' AND confirmable_at <= now() LOOP
        PERFORM coin_lock_balance(v_user);
        WITH c AS (
            UPDATE coin_ledger_entries SET status = 'confirmed'
             WHERE user_id = v_user AND status = 'pending' AND confirmable_at <= now() RETURNING amount)
        SELECT coalesce(sum(amount), 0), count(*) INTO s, n FROM c;
        UPDATE coin_balances
           SET pending_balance = pending_balance - s, confirmed_balance = confirmed_balance + s,
               lifetime_earned = lifetime_earned + s
         WHERE user_id = v_user;
        total := total + n;
    END LOOP;
    RETURN total;
END $$;

-- Spend confirmed coins. Raises TC011 when the confirmed balance is insufficient. Idempotent.
CREATE OR REPLACE FUNCTION coin_spend(p_user uuid, p_amount bigint, p_idempotency_key text,
                                      p_reference_type text DEFAULT NULL, p_reference_id uuid DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    b coin_balances;
    v_entry uuid;
BEGIN
    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'telcron: spend amount must be positive' USING ERRCODE = 'TC011';
    END IF;
    b := coin_lock_balance(p_user);
    SELECT id INTO v_entry FROM coin_ledger_entries WHERE idempotency_key = p_idempotency_key;
    IF FOUND THEN RETURN v_entry; END IF;
    IF b.confirmed_balance < p_amount THEN
        RAISE EXCEPTION 'telcron: insufficient confirmed TelCoins (have %, need %)', b.confirmed_balance, p_amount
            USING ERRCODE = 'TC011';
    END IF;
    INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, reference_type, reference_id, idempotency_key)
    VALUES (p_user, 'spend', -p_amount, 'confirmed', p_reference_type, p_reference_id, p_idempotency_key)
    RETURNING id INTO v_entry;
    UPDATE coin_balances SET confirmed_balance = confirmed_balance - p_amount WHERE user_id = p_user;
    RETURN v_entry;
END $$;

-- Claw back an earn/bonus entry (e.g. its review was removed). Pending/frozen ⇒ reversed in place;
-- confirmed ⇒ a negative clawback entry (balance may go negative: debt repaid by future earnings).
-- Also claws back the entry's level bonus. Idempotent.
CREATE OR REPLACE FUNCTION coin_clawback(p_entry uuid) RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE
    e coin_ledger_entries;
    v_claw uuid;
    v_bonus uuid;
BEGIN
    SELECT * INTO STRICT e FROM coin_ledger_entries WHERE id = p_entry;
    IF e.entry_type NOT IN ('earn', 'level_bonus') THEN
        RAISE EXCEPTION 'telcron: only earn/level_bonus entries can be clawed back' USING ERRCODE = 'TC012';
    END IF;
    PERFORM coin_lock_balance(e.user_id);
    SELECT * INTO STRICT e FROM coin_ledger_entries WHERE id = p_entry;   -- re-read under lock

    FOR v_bonus IN SELECT id FROM coin_ledger_entries
                    WHERE entry_type = 'level_bonus' AND reference_type = 'ledger_entry' AND reference_id = p_entry LOOP
        PERFORM coin_clawback(v_bonus);
    END LOOP;

    IF e.status = 'reversed' THEN
        RETURN NULL;
    ELSIF e.status IN ('pending', 'frozen') THEN
        UPDATE coin_ledger_entries SET status = 'reversed' WHERE id = p_entry;
        UPDATE coin_balances
           SET pending_balance = pending_balance - CASE WHEN e.status = 'pending' THEN e.amount ELSE 0 END,
               frozen_balance  = frozen_balance  - CASE WHEN e.status = 'frozen'  THEN e.amount ELSE 0 END
         WHERE user_id = e.user_id;
        RETURN NULL;
    END IF;

    SELECT id INTO v_claw FROM coin_ledger_entries WHERE reverses_entry_id = p_entry AND entry_type = 'clawback';
    IF FOUND THEN RETURN v_claw; END IF;
    INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, reverses_entry_id, idempotency_key)
    VALUES (e.user_id, 'clawback', -e.amount, 'confirmed', p_entry, 'clawback:' || p_entry)
    RETURNING id INTO v_claw;
    UPDATE coin_balances
       SET confirmed_balance = confirmed_balance - e.amount,
           lifetime_earned   = greatest(lifetime_earned - e.amount, 0)
     WHERE user_id = e.user_id;
    RETURN v_claw;
END $$;

-- Redeem a catalogue item: spend + redemption row in one transaction. Idempotent on p_idempotency_key.
CREATE OR REPLACE FUNCTION coin_redeem(p_user uuid, p_item text, p_idempotency_key text, p_product uuid DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    it redemption_items;
    v_id uuid := uuidv7();
    v_spend uuid;
    v_existing uuid;
BEGIN
    SELECT * INTO it FROM redemption_items WHERE code = p_item AND is_active;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'telcron: unknown or inactive redemption item %', p_item USING ERRCODE = 'TC011';
    END IF;
    v_spend := coin_spend(p_user, it.cost_coins, 'redeem:' || p_idempotency_key, 'redemption', v_id);
    SELECT id INTO v_existing FROM redemptions WHERE ledger_entry_id = v_spend;
    IF FOUND THEN RETURN v_existing; END IF;
    INSERT INTO redemptions (id, user_id, item_code, ledger_entry_id, product_id)
    VALUES (v_id, p_user, p_item, v_spend, p_product);
    RETURN v_id;
END $$;

-- A user's reward level (derived from lifetime earned; never decreases by spending).
CREATE OR REPLACE FUNCTION telcron_reward_level(p_user uuid) RETURNS reward_levels
LANGUAGE sql STABLE AS $$
    SELECT l.* FROM reward_levels l
     WHERE l.min_lifetime_coins <= coalesce((SELECT lifetime_earned FROM coin_balances WHERE user_id = p_user), 0)
     ORDER BY l.min_lifetime_coins DESC LIMIT 1
$$;

-- ─────────────── Community counters ───────────────
CREATE OR REPLACE FUNCTION telcron_post_counters() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    d int := CASE WHEN TG_OP = 'INSERT' THEN 1 ELSE -1 END;
    rec record;
BEGIN
    IF TG_OP = 'INSERT' THEN rec := NEW; ELSE rec := OLD; END IF;
    IF TG_TABLE_NAME = 'comments' AND rec.post_id IS NOT NULL THEN
        UPDATE posts SET comment_count = comment_count + d WHERE id = rec.post_id;
    ELSIF TG_TABLE_NAME = 'reactions' THEN
        UPDATE posts SET reaction_count = reaction_count + d WHERE id = rec.post_id;
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER comments_counters AFTER INSERT OR DELETE ON comments
    FOR EACH ROW EXECUTE FUNCTION telcron_post_counters();
CREATE TRIGGER reactions_counters AFTER INSERT OR DELETE ON reactions
    FOR EACH ROW EXECUTE FUNCTION telcron_post_counters();

-- Community feed (TC-P1-025): posts, reviews and hazard flags in one stream.
CREATE OR REPLACE VIEW community_feed AS
    SELECT 'post'::text AS kind, p.id, p.product_id, p.author_user_id, p.body AS body, p.geohash, p.created_at
      FROM posts p WHERE p.status = 'published' AND p.deleted_at IS NULL
    UNION ALL
    SELECT 'review', r.id, r.product_id, r.author_user_id, r.body, r.geohash, r.created_at
      FROM reviews r WHERE r.origin = 'user' AND r.status = 'published' AND r.deleted_at IS NULL
    UNION ALL
    SELECT 'hazard_flag', f.id, f.product_id, f.reporter_user_id, f.description, f.geohash, f.created_at
      FROM hazard_flags f WHERE f.status <> 'rejected';

-- ─────────────── Risk fan-out ───────────────
-- Creates one timeline alert per affected user (wallet holders with alerts on + watchers), honouring
-- recall geography (TC-P1-010 AC4/5: regional recalls only reach users in that region; users with
-- unknown location are alerted). Idempotent: safe to run on every re-screen.
CREATE OR REPLACE FUNCTION telcron_fanout_risk_event(p_event uuid) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    n integer;
BEGIN
    WITH ev AS (SELECT * FROM risk_events WHERE id = p_event),
    holders AS (
        SELECT w.user_id, w.id AS wallet_item_id FROM wallet_items w, ev
         WHERE w.product_id = ev.product_id AND w.deleted_at IS NULL AND w.alerts_enabled AND w.status = 'active'
        UNION ALL
        SELECT pw.user_id, NULL FROM product_watches pw, ev
         WHERE pw.product_id = ev.product_id AND (pw.expires_at IS NULL OR pw.expires_at > now())
    ),
    eligible AS (
        SELECT DISTINCT ON (h.user_id) h.user_id, h.wallet_item_id
          FROM holders h JOIN users u ON u.id = h.user_id, ev
         WHERE u.deleted_at IS NULL
           AND (ev.recall_id IS NULL
                OR NOT EXISTS (SELECT 1 FROM recall_regions rr WHERE rr.recall_id = ev.recall_id)
                OR u.country_code IS NULL
                OR EXISTS (SELECT 1 FROM recall_regions rr
                            WHERE rr.recall_id = ev.recall_id AND rr.country_code = u.country_code
                              AND (rr.subdivision_code = '' OR rr.subdivision_code = u.subdivision_code
                                   OR u.subdivision_code IS NULL)))
         ORDER BY h.user_id, h.wallet_item_id NULLS LAST
    ),
    ins AS (
        INSERT INTO user_risk_alerts (user_id, risk_event_id, wallet_item_id)
        SELECT user_id, p_event, wallet_item_id FROM eligible
        ON CONFLICT (user_id, risk_event_id) DO NOTHING RETURNING 1)
    SELECT count(*) INTO n FROM ins;
    RETURN n;
END $$;
