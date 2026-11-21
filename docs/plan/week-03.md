# Week 3 · Sat 28 Nov – Fri 4 Dec · Google sign-in, categories by configuration, first marketplace source, dead letters

## Goal
Finish the parts of identity and ingestion that need no outside decision except D7/D8, and make failures recoverable.

## Starting point
Ingestion handles CPSC and research only; dead letters are parked in Redis with no way back; categories are fixed in seed data; audit entries cover six modules of nine.

## Work orders

- **WO-025 · Google sign-in** (`platform-identity-engineer, frontend-engineer`): Sign in and sign up with Google; an existing email account links rather than duplicates; the email counts as verified; tokens never logged; journey test.
- **WO-026 · Audit log everywhere** (`tech-lead → platform-identity, community-rewards, data-ai`): Every state change in wallet, redemptions and coin spending, and admin source/schedule changes writes `audit()` with actor, action, target and request id; a test per module.
- **WO-027 · Categories by configuration** (`catalogue-engineer, data-ai-engineer, frontend-engineer`): Adding a category is a row plus a source config — no deploy (F9); the three launch categories (D8) configured; admin page to view and edit them.
- **WO-003b · First marketplace source** (`data-ai-engineer`): One source per D7 behind the adapter, its access method and terms in `data_sources.config`, raw payload kept, contract fixture recorded, rate limit respected; listings become aliases of one product.
- **WO-028 · Dead letters and raw copies** (`data-ai-engineer, frontend-engineer`): Admin view of dead letters; replay one or all; a replayed job runs once (idempotent); barcode and vision lookups keep raw responses.
- **WO-029 · Schema: review-task types** (`database-engineer`): DEF-007 item 1: task types for Medium and High results (spec first, migration, drift); the rest of DEF-007 settled with the schema author (D14).

## Decisions due by the end of this week
D2 QA/production environments · D14 schema author's review.

## Performance plan
Marketplace runs skip unchanged pages (payload hash); ingestion never blocks the API; the new admin lists paginate.

## Friday demo
Google sign-in; a category added without a deploy; a marketplace listing becoming an alias; a dead letter replayed.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
