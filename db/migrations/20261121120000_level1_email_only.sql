-- Level 1 needs a verified email; a verified phone is no longer required (ADR-006, 2026-11-21).
-- Hand-written. No SMS route exists yet, and sending SMS to India needs DLT registration first.
-- Restore the phone requirement with a new migration once phone codes can be delivered.

-- migrate:up
ALTER TABLE users DROP CONSTRAINT users_chk3;
ALTER TABLE users ADD CONSTRAINT users_chk3
    CHECK (verification_level = 0 OR email_verified_at IS NOT NULL);

-- migrate:down
ALTER TABLE users DROP CONSTRAINT users_chk3;
ALTER TABLE users ADD CONSTRAINT users_chk3
    CHECK (verification_level = 0 OR (email_verified_at IS NOT NULL AND phone_verified_at IS NOT NULL));
