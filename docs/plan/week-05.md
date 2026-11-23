# Week 5 · Sat 12 – Fri 18 Dec · Wallet watches and email alerts; Medium/High review; AI log and cache

## Goal
Owners hear about a change to something they own, risky results reach a human, and every AI call is accounted for.

## Starting point
Wallet saves and in-app alerts only; Medium/High results do not open review tasks; only hazard scoring is logged, without cost; no AI result cache.

## Work orders

- **WO-033 · Wallet labels, watches, email alerts** (`community-rewards-engineer, frontend-engineer`): Labels on wallet items; watch a product without owning it; the extra-watches redemption raises the limit; a passport change sends an email (D15) and an in-app alert, once. **Must also re-activate the `watchlist_3` store item** (`is_active = true`, a new data migration), which WO-059 took off sale on 2026-11-23 (D13 amendment, DEF-117), and only once a member's watch limit actually reads the `watchlist_slots` entitlement; re-add it to CT-004's store and test that a purchase raises the limit.
- **WO-034 · Medium/High to review; High blocked** (`data-ai-engineer`): Every Medium or High result opens a review task; High is marked blocked until reviewed and an admin is alerted (tech doc §7.4); tests for both.
- **WO-035 · AI log with cost, AI cache** (`data-ai-engineer`): Every AI call (scoring, vision, Rekognition, research, assistant, embedder) writes `ai_invocations` with model, prompt version, tokens, latency and cost; results cached 24 h per product and model version.
- **WO-036 · Business accounts schema** (`database-engineer`): Per D6: accounts, API keys (hashed), webhooks and deliveries — spec first, migration, drift, tests.

## Decisions due by the end of this week
D9 trust-score formula.

## Performance plan
Email sending in the Worker only; alert fan-out bounded and batched; cache hit ratio measured.

## Friday demo
Watch a product, change its passport, receive the email. A High result appearing in the safety queue.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
