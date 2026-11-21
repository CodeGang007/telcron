# ADR-006: Level 1 needs a verified email only, for now

Date: 2026-11-21 · Status: accepted (by the human, in chat)

## Context
Level 1 (allowed to contribute) required a verified email and a verified phone, enforced by the
database (`users.users_chk3`). The deployed site could send neither. Email now goes through Amazon
SES. SMS costs money per message, and SMS to Indian numbers needs DLT sender registration first.

## Decision
Level 1 requires a verified email. The phone number is optional at sign-up and kept if given, but
not verified. Migration `20261121120000_level1_email_only` replaces the check; the API setting
`LEVEL1_REQUIRES_PHONE` (default off) issues phone codes again when on.

## Consequences
- One person can hold several Level 1 accounts with different emails: the phone was the main
  duplicate-account defence (one verified owner per number). Coin fraud holds and the daily cap
  still apply. Revisit before rewards have real value.
- To restore: an SMS route, then a new migration restoring the phone condition, then
  `LEVEL1_REQUIRES_PHONE=true`.
