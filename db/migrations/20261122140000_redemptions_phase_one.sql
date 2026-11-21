-- Redemptions: phase one sells two items, and no redemption is left `processing` (WO-019, decision D13).
-- Hand-written. Only the printable hazard report (`pdf_report`) and extra watches (`watchlist_slots`) are
-- phase one (tech doc §2.2, §9.4); the other items took coins and were never fulfilled. They go off sale,
-- and every redemption still `processing` for an item that is off sale is refunded through
-- coin_refund_redemption(). Safe to run on any database: on a fresh one nothing is refunded.

-- migrate:up

-- Refund a redemption that was not delivered: one confirmed `refund` entry reverses its spend, the coins
-- return to the confirmed balance (lifetime earned is unchanged: spending never lowered it), and the
-- redemption becomes `refunded` with the refund recorded in `fulfilment`. Only `processing` or `failed`
-- redemptions with no entitlement granted can be refunded. Idempotent: a repeat returns the same refund
-- entry and pays nothing (the partial unique index on reverses_entry_id backs this up).
CREATE OR REPLACE FUNCTION coin_refund_redemption(p_redemption uuid, p_reason text DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
    r redemptions;
    s coin_ledger_entries;
    v_refund uuid;
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

    IF r.status NOT IN ('processing', 'failed') THEN
        RAISE EXCEPTION 'telcron: redemption % is %; only processing or failed redemptions are refunded',
            r.id, r.status USING ERRCODE = 'TC013';
    END IF;
    IF EXISTS (SELECT 1 FROM user_entitlements WHERE redemption_id = r.id) THEN
        RAISE EXCEPTION 'telcron: redemption % granted an entitlement; it was delivered', r.id
            USING ERRCODE = 'TC013';
    END IF;

    INSERT INTO coin_ledger_entries (user_id, entry_type, amount, status, reverses_entry_id,
                                     reference_type, reference_id, idempotency_key)
    VALUES (r.user_id, 'refund', -s.amount, 'confirmed', s.id, 'redemption', r.id, 'refund:' || s.id)
    RETURNING id INTO v_refund;
    UPDATE coin_balances SET confirmed_balance = confirmed_balance - s.amount WHERE user_id = r.user_id;
    UPDATE redemptions
       SET status = 'refunded',
           fulfilment = coalesce(fulfilment, '{}'::jsonb)
                        || jsonb_build_object('refund', jsonb_build_object('ledger_entry_id', v_refund,
                                                                           'reason', p_reason))
     WHERE id = r.id;
    RETURN v_refund;
END $$;

UPDATE redemption_items SET is_active = false
 WHERE is_active AND fulfilment_type NOT IN ('pdf_report', 'watchlist_slots');

SELECT coin_refund_redemption(r.id, 'item withdrawn from sale (D13)')
  FROM redemptions r JOIN redemption_items i ON i.code = r.item_code
 WHERE r.status = 'processing' AND NOT i.is_active
 ORDER BY r.created_at;

-- migrate:down
-- The items stay off sale and the refunds stay in the ledger (append-only); only the function goes.
DROP FUNCTION IF EXISTS coin_refund_redemption(uuid, text);
