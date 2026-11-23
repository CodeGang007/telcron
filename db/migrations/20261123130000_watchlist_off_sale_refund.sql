-- "Watchlist alerts for 3 products" goes off sale until watches exist, and every buyer is refunded
-- (DEF-117, WO-059; the human chose option (a) on 2026-11-23). Hand-written.
-- Nothing reads a `watchlist_slots` entitlement yet (watches are WO-033), so the 100 coins bought nothing.
-- coin_refund_redemption() rightly refuses a fulfilled redemption and one that granted an entitlement, and
-- keeps doing so. This adds a second, narrow refund: coin_refund_withdrawn_redemption() reverses only a
-- fulfilled redemption of an item that is now off sale, whose fulfilment is `watchlist_slots`, and whose
-- entitlement no watch uses; it deletes that entitlement in the same call. A delivered hazard report, or
-- anything still on sale, is refused.
-- redemptions_chk1 used to force fulfilled_at to be NULL on any status but `fulfilled`; a refunded
-- redemption that had been delivered now keeps its fulfilled_at (spec: Revised check).
-- Safe to run on any database and to run again: a refunded redemption is never refunded twice.

-- migrate:up
ALTER TABLE redemptions DROP CONSTRAINT redemptions_chk1;
ALTER TABLE redemptions ADD CONSTRAINT redemptions_chk1
    CHECK ((status = 'fulfilled' AND fulfilled_at IS NOT NULL) OR (status IN ('processing', 'failed') AND fulfilled_at IS NULL) OR status = 'refunded');

-- Refund a delivered redemption of an item withdrawn from sale whose only delivery is unused watchlist
-- slots: one confirmed `refund` entry reverses its spend, the coins return to the confirmed balance
-- (lifetime earned is unchanged: spending never lowered it), its entitlement rows are deleted and recorded
-- in fulfilment.refund.revoked_entitlements, and the redemption becomes `refunded`. Idempotent: a repeat
-- returns the same refund entry and pays nothing (the partial unique index on reverses_entry_id and the
-- idempotency key `refund:<spend>` back this up, shared with coin_refund_redemption()).
CREATE OR REPLACE FUNCTION coin_refund_withdrawn_redemption(p_redemption uuid, p_reason text DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    r redemptions;
    it redemption_items;
    s coin_ledger_entries;
    v_refund uuid;
    v_revoked jsonb;
BEGIN
    SELECT * INTO r FROM redemptions WHERE id = p_redemption;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'telcron: unknown redemption %', p_redemption USING ERRCODE = 'TC013';
    END IF;
    PERFORM coin_lock_balance(r.user_id);
    SELECT * INTO STRICT r FROM redemptions WHERE id = p_redemption FOR UPDATE;     -- re-read under lock
    SELECT * INTO STRICT s FROM coin_ledger_entries WHERE id = r.ledger_entry_id;

    SELECT id INTO v_refund FROM coin_ledger_entries WHERE reverses_entry_id = s.id AND entry_type = 'refund';
    IF FOUND THEN RETURN v_refund; END IF;                                          -- already refunded

    SELECT * INTO STRICT it FROM redemption_items WHERE code = r.item_code FOR SHARE; -- no re-listing meanwhile
    IF r.status <> 'fulfilled' THEN
        RAISE EXCEPTION 'telcron: redemption % is %; only a fulfilled redemption of a withdrawn item is refunded here '
            '(use coin_refund_redemption)', r.id, r.status USING ERRCODE = 'TC013';
    END IF;
    IF it.is_active THEN
        RAISE EXCEPTION 'telcron: item % is on sale; its delivered redemptions are not refunded', it.code
            USING ERRCODE = 'TC013';
    END IF;
    IF it.fulfilment_type <> 'watchlist_slots' THEN
        RAISE EXCEPTION 'telcron: item % delivers %; only unused watchlist slots can be taken back', it.code,
            it.fulfilment_type USING ERRCODE = 'TC013';
    END IF;
    IF EXISTS (SELECT 1 FROM user_entitlements e WHERE e.redemption_id = r.id AND e.entitlement <> 'watchlist_slots') THEN
        RAISE EXCEPTION 'telcron: redemption % granted something other than watchlist slots', r.id
            USING ERRCODE = 'TC013';
    END IF;
    PERFORM 1 FROM user_entitlements e WHERE e.redemption_id = r.id FOR UPDATE;    -- no new watch meanwhile
    IF EXISTS (SELECT 1 FROM product_watches w JOIN user_entitlements e ON e.id = w.entitlement_id
                WHERE e.redemption_id = r.id) THEN
        RAISE EXCEPTION 'telcron: redemption % is in use by a product watch', r.id USING ERRCODE = 'TC013';
    END IF;

    WITH gone AS (
        DELETE FROM user_entitlements WHERE redemption_id = r.id
        RETURNING id, entitlement, quantity, starts_at, ends_at
    )
    SELECT coalesce(jsonb_agg(jsonb_build_object('id', id, 'entitlement', entitlement, 'quantity', quantity,
                                                 'starts_at', starts_at, 'ends_at', ends_at) ORDER BY id),
                    '[]'::jsonb)
      INTO v_revoked FROM gone;

    INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, reverses_entry_id,
                                     reference_type, reference_id, idempotency_key)
    VALUES (r.user_id, 'refund', -s.amount, 'confirmed', s.id, 'redemption', r.id, 'refund:' || s.id)
    RETURNING id INTO v_refund;
    UPDATE coin_balances SET confirmed_balance = confirmed_balance - s.amount WHERE user_id = r.user_id;
    UPDATE redemptions
       SET status = 'refunded',
           fulfilment = coalesce(fulfilment, '{}'::jsonb)
                        || jsonb_build_object('refund', jsonb_build_object('ledger_entry_id', v_refund,
                                                                           'reason', p_reason,
                                                                           'revoked_entitlements', v_revoked))
     WHERE id = r.id;
    RETURN v_refund;
END $$;

UPDATE redemption_items SET is_active = false WHERE code = 'watchlist_3' AND is_active;

SELECT coin_refund_withdrawn_redemption(r.id, 'item withdrawn from sale until watches exist (DEF-117)')
  FROM redemptions r
 WHERE r.item_code = 'watchlist_3' AND r.status = 'fulfilled'
 ORDER BY r.created_at, r.id;

-- migrate:down
-- The refunds stay in the ledger (append-only) and the redemptions stay `refunded`; watchlist_3 stays off
-- sale (putting it back on sale is WO-033's own migration, once watches exist). The function goes. The old
-- redemptions_chk1 comes back only if no refunded redemption kept its fulfilled_at; otherwise the revised
-- rule stays, because the old one would reject rows this migration legitimately wrote.
DROP FUNCTION IF EXISTS coin_refund_withdrawn_redemption(uuid, text);
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM redemptions WHERE status = 'refunded' AND fulfilled_at IS NOT NULL) THEN
        ALTER TABLE redemptions DROP CONSTRAINT redemptions_chk1;
        ALTER TABLE redemptions ADD CONSTRAINT redemptions_chk1 CHECK ((status = 'fulfilled') = (fulfilled_at IS NOT NULL));
    END IF;
END $$;
