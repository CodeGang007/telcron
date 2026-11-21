# WO-017 — final QA, part A (backend and schema) — PLAN §5 check 1

qa-test-engineer · 2026-11-22 · worktree `wt-qa-final-a`, branch `wt/qa-final-a` @ 838beea (= `week-02`)
Lane: Postgres 127.0.0.1:55444, Redis 127.0.0.1:63844. No shared DB 5433, no AWS, no provider calls, no push.

## Verdict: APPROVE WITH NITS
Every item in scope passes its acceptance, and every revert proof below is my own mutation. Each went red and
was restored, and `git diff` was empty afterwards. Two new defects were found, neither of them blocking for
this scope: DEF-080 (search performance, S3) and DEF-081 (concurrent register gives a 500, S4).

## Gates (run by me, this worktree, this lane)
| Gate | Result |
| --- | --- |
| `cd backend && uv run ruff check .` | `All checks passed!` |
| `cd backend && uv run pytest -q` | `143 passed, 4 warnings in 32.33s` (warnings: Starlette 422-constant deprecation) |
| `pytest db/tests --ignore=db/tests/test_performance.py -q` | `94 passed in 5.55s` |
| `pytest db/tests/test_performance.py -q -s` | `13 passed in 62.03s` (numbers below) |
| `make db-gen` | regenerated; `git status` shows no change, so byte-for-byte |
| tsc / build / journey | not run: part A is backend and schema only (part B covers them) |

## Items
| Item | Verdict | Evidence | My revert proof (red → restored) |
| --- | --- | --- | --- |
| WO-019 | PASS | After `dbmate up` the active items are `hazard_report_pdf,watchlist_3` (6 before). Refund function present; store lists active only. | Commented out `UPDATE coin_balances SET confirmed_balance …` in `coin_refund_redemption` (migration 140000:45): `db/tests/test_redemptions.py` 3 failed, `backend/tests/test_redemptions.py` 1 failed. Dropped `.where(RedemptionItem.is_active)` (`rewards/router.py:114`): `test_the_store_lists_only_the_phase_one_items` failed. |
| WO-022 | PASS | (1) Old path (pre-41bdc29 migrations, `001`, then the five `db/schema-next` files, as the old `make db-next` did) vs. a fresh `dbmate up` + `001`: normalised `pg_dump --schema-only` (PG18) differs by **38 lines, all inside `coin_refund_redemption`**, which WO-019 added later. Outside that function the diff is 0. (2) `dbmate up` on the old-path DB (phases present) applied all six new migrations without error. Its schema afterwards equals the fresh build exactly (**0 lines**). (3) `dbmate rollback`: 140000 rolls back, then 130400 is refused, `pq: irreversible: phase 2-3 reference rows (S-18)…`. `coin_balances`, `redemptions` and `hazard_assessments` are still there. All five promoted downs raise. (4) `make db-gen` produced no change. | S-18: replaced the phase-3 down's `RAISE` with `DROP TABLE IF EXISTS coin_balances CASCADE`: `test_rolling_back_a_promoted_migration_is_refused_and_changes_nothing[…phase3_schema]` failed (1 failed, 11 passed). |
| WO-054 | PASS (PARTIAL by design: unwired on dev, human step) | `raw_store: str = "none"` by default (`core/config.py:88`). The s3 test checks that the key is set, `sha256(stored) == payload_sha256`, and that a repeat stores nothing. Key XOR payload follows `source_records_chk1` (departure accepted by tech-lead). | Key-setting line in `_store_recall` forced to `payload=record, payload_storage_key=None`: `test_with_the_raw_store_on_each_new_record_is_kept_outside_the_database` and `test_research_keeps_the_raw_copy_of_each_new_cpsc_notice` failed. `keep_raw` catch narrowed to `ZeroDivisionError`: `test_a_failed_upload_keeps_the_record_in_the_database` failed. |
| WO-056 (server) | PASS | Through the real `app.main` (registered at `main.py:47`) with rows `qa_on=true`, `qa_off=false`: `200 public, max-age=60 {"flags":{"qa_on":true}}`. A bad bearer token still gets 200, so the route is public. `is_enabled` gives `qa_on` True, `qa_off` False, absent False. `grep` finds no other server-side reader of `feature_flags`. CT-001 is met exactly. | Enabled filter removed from `enabled_codes`: `test_the_list_holds_only_enabled_flags` failed. `is_enabled` selecting `code` instead of `is_enabled`: `test_a_disabled_flag_is_off` failed. |
| WO-057 | PASS | 20 cases. New: children's (highchair-tip, button-cell-toy, teether-no-recall), small kitchen (air-fryer-overheat, pressure-cooker-lid, coffee-maker-fine), chargers/electronics (power-bank-recall, earbuds-certified). Each names a `none` dimension, and four have no recall. `about` says REGRESSION BASELINE. Offline run (`AI_PROVIDER=stub`, keys blank): `answered by stub-heuristic-0: agreement 96% on 54 graded dimensions, citation validity 100%`. Misses: prompt-injection regulatory, pressure-cooker-lid health_safety. No live-model run (no key). | Dropped the last case from `cases.json`: `test_the_baseline_has_twenty_well_formed_cases` failed. |
| DEF-010 | PASS | `db/tests/test_sample_data.py` green. Seed rows have hazard NULL and trust 23.33 / 95.00 / 66.67. | Northwind trust 95.00 → 96.00 with hazard still NULL: `test_demo_passports_are_what_the_passport_rule_would_issue` failed. |
| DEF-011 (S2) | PASS | Test: claim, reject, confirm and dismiss by the held moderator each give `403 own_item`. Balances stay `(0,0,105)`, the hold stays `open`, and a colleague's release gives `(105,0,0)`. | Removed `fraud_hold` from `SUBJECT_OWNER` (falls back to the submitter): `test_a_moderator_cannot_release_their_own_fraud_hold` failed. |
| DEF-012 | PASS | Dismiss releases the hold, and closes a flag or report as `rejected` with no penalty. | Flag dismiss early-return disabled (falls into the rejection penalty): `test_dismissing_a_flag_closes_it_without_a_penalty` failed. |
| DEF-022 | PASS | `AskIn.thread_id: uuid.UUID \| None`, so a malformed id is a 422. | Type back to `str \| None`: the test failed with `DBAPIError invalid input … 'not-a-uuid'`. |
| DEF-032 | PASS | A re-screen reuses the open task and moves it to the newest assessment. | `task.subject_id = assessment_id` replaced by `pass`: `test_a_rescreen_reuses_the_open_missing_evidence_task_for_the_product` failed. |
| DEF-041 | PASS | Exact regulator hosts only. | Subdomains of regulators trusted (`host.endswith("."+r)`): `test_only_the_regulators_own_hosts_are_official` failed. |
| DEF-042 | PASS | Anonymous callers get the cache only, with `not_authenticated`. | Router `refused = None if user is None`: `test_an_anonymous_visitor_sees_cached_listings_only_and_starts_no_search` failed. |
| DEF-043 | PASS (see DEF-081) | Same register answer for new and existing addresses; locked account gives 401; dummy argon2. | Existing address returns `email_sent=False` (no notice): `test_register_answers_the_same_whether_or_not_the_address_has_an_account` failed. |
| DEF-044 | PASS | 429 `rate_limited` + `Retry-After` on the four routes, per IP and per address. | `count > limit` → `count > limit + 1`: 6 failed (login per address, 4× per-IP routes, verify per address). |
| DEF-048 | PASS | The validator refuses `DEV_EXPOSE_CODES` outside local/test. The host runs `ENV=dev` (`infra/aws/deploy-host.sh:90`), which is the case the test covers. | Added `"dev"` to the allowed envs: `test_exposed_codes_are_refused_outside_local_and_test` failed. |
| DEF-049 | PASS | Error codes only, a per-user daily share, and a listing check. | Quota `>=` → `>` (off by one): `test_one_member_cannot_spend_more_than_their_daily_research_share` failed. `_public_stats` emitting the raw error text: `test_research_errors_reach_the_page_as_codes_only` failed. |
| DEF-060 | PASS | `Revised` check; `db/tests/test_spec_checks.py` green. | Spec `users_chk3` widened with `OR phone_verified_at IS NOT NULL`: both spec-check tests failed. |
| DEF-070 | PASS | conftest replaces `cpsc.search` and `cpsc.fetch`. | Both conftest lines removed: `test_research_never_reaches_the_cpsc_registry` failed. |
| S-18 | PASS | See WO-022: rollback is refused live with dbmate and the tables stay. | See WO-022 (phase-3 down made to drop the ledger table: red). |
| S-20 | PASS | A task type outside `SUBJECT_OWNER` falls back to `submitted_by_user_id`. | Fallback made to `return None`: `test_staff_cannot_decide_a_task_they_submitted_of_an_unlisted_type` failed. |
| S-21 | PASS | `research_per_user_per_day: int = 5` (`core/config.py:83`). Env `RESEARCH_PER_USER_PER_DAY=2` makes `_per_user_daily()` return 2, `abc` is refused at startup (pydantic `int_parsing`), and the default is 5. | Behavioural probe above. The quota mutation under DEF-049 covers the check that reads it. |

## Performance
- **Schema at volume** (`test_performance.py`: 100 000 products, 200 000 aliases, 100 000 passports, 300 000 ledger
  rows, …). All 13 cases are index-backed. Public passport page (slug → current passport) 0.07 ms · barcode
  0.05 ms · fuzzy product search, KNN form, 19.73 ms · recall KNN 2.95 ms · the rest ≤ 0.11 ms.
- **HTTP.** `uvicorn app.main:app` (one worker) on a throwaway lane DB: `dbmate up` + `001` + demo data + 50 000
  synthetic products. Redis on lane db 1. Measured with `curl -w %{time_total}` from the same host, nothing else
  running:
  - Cached passport read (`GET /products/northwind-chillmate-31/passport`): cold 33 ms (cache miss; this request
    filled `telcron:passport:<id>`). Then n=100 **p50 6.4 ms, p95 8.1 ms, max 10.7 ms**. Acme: p50 6.2 / p95 8.1 ms.
    **Target < 300 ms: met.**
  - Text search `GET /products?q=…` (n=30 each): `blender` p50 233.7 / p95 273.2 ms · `blendr` p50 237.2 / p95 262.8 ms ·
    `power bank ultra` p50 358.6 / p95 401.0 ms · model number `QA-12345` p50 11.9 / p95 12.7 ms (exact branch).
    The fuzzy branch seq-scans `products` (EXPLAIN: 375 ms); the KNN form on the same data takes 4.5 ms using
    `products_i1_idx`. Filed as **DEF-080**.

## New defects
- **DEF-080** (S3, catalogue-engineer): text search scans every product, 230–400 ms at 50 000. The fix is the KNN form.
- **DEF-081** (S4, platform-identity-engineer): concurrent registrations of one new address give one 201 and the
  rest 500 (`users_email_key`, `identity/service.py:112`). Reproduced 5/5. DEF-043 flagged this but did not file it.

## Nits (not blocking)
- `research/service.py:127` still reads the setting with `getattr(..., PER_USER_DAILY)` even though the typed
  field exists (S-21). The fallback constant is dead code now.
- DEF-011 suggested also refusing self-release inside `coin_resolve_hold` (database-engineer). Not done: the rule
  holds only in the service. It is optional in the defect.
- WO-019: no `coin_*` function writes `audit_log`. The engineer flagged this; WO-026 covers it.

## Good
- S-18's irreversible downs are now a standing test (`test_migrations.py`), and they hold against real `dbmate`.
- DEF-060's spec-versus-database CHECK comparison closes a whole class of silent drift that the drift test could not see.

## Not checked
- Frontend parts of WO-056 and the web side of the defects: part B.
- Behaviour on the AWS dev host (no access by design). The S-18 refusal and WO-022's skip path were checked on a
  lane copy of the pre-WO-022 shape, not on dev.
- WO-057 with a live model (no key configured).

Worktree left clean: HEAD 838beea, no diff, no commits added. `frontend/node_modules` was already untracked
before this run. Throwaway DBs `qa_old` and `qa_new` were dropped, and lane Redis db 1 was flushed.

## Last re-check (bdc4c57)
qa-test-engineer, 2026-11-22. Worktree `wt-qa-last` (`wt/qa-last` @ bdc4c57 = `week-02`), lane PG :55444 / Redis :63844.
Scope: `git diff 838beea..bdc4c57`, 8 commits. DEF-090 (tech-lead bookkeeping) was skipped as asked.

Verdict: **APPROVE WITH NITS**. Two new defects, neither blocking: DEF-110 (S3) and DEF-111 (S4).

| Item | Verdict | Independent proof |
| --- | --- | --- |
| DEF-080 search (catalogue) | PASS, with DEF-110 open | Search reverted to 838beea: `test_search.py` **4 passed**, so the tests guard answers, not the plan (DEF-110). Mutations, each red then restored: part list dropped → `test_a_fragment_inside_a_word…` failed; brand list dropped → `test_a_brand_finds…` failed; ties ordered by name → `test_pages_continue_each_other_through_ties` failed. |
| DEF-080 index (schema) | PASS | Migration `20261122150000_products_brand_index.sql` removed → `test_spec_indexes.py` **6 failed, 1 passed**; restored → green. `make db-gen` byte-identical. |
| DEF-081 register race | PASS | `identity/service.py` reverted → race test FAILED (IntegrityError 500). Savepoint removed → FAILED. Constraint name changed to `no_such_key` → FAILED (so the name is really read). 5 repeat runs: 5 × `1 passed`. |
| DEF-100 auth unreachable (frontend) | PASS (code review), DEF-111 open | `lib/auth.tsx` reverted → `tsc`: `Gate.tsx(38,24)` and `Layout.tsx(141,15)` `Property 'unreachable' does not exist`. 4xx still signs out; network/5xx keeps the session; Try again is 44 px and calls `reload()`. There are no frontend unit tests, so the behaviour was not run by me. The admin area's own gate was missed: DEF-111. |
| DEF-101 `mine` (backend) | PASS | `modules/moderation/` reverted → `test_the_queue_marks_a_reviewers_own_items_as_mine` FAILED. Mutations `mine = submitted_by == viewer` and `mine = False` → FAILED. Owner read off the row already loaded, so no extra query. |
| DEF-101 (frontend) | PASS (code review) | `useState(!!task.mine)` hides the decisions up front, and an `own_item` 403 also hides them. Buttons are `min-h-11`. |
| DEF-023 agent paths | PASS | `community-rewards-engineer` gains `modules/moderation/**`. `data-ai-engineer` gains ingestion, research, assistant, evals and embedder. Both match `telcron-domain-map` rows 15–16, and each path is claimed by exactly one agent file (grep). |

**Search timing at 50 004 products** (`qa_last_perf` = `telcron_api_test` + 50 000 synthetic, `ANALYZE`; uvicorn, no
embedder, HTTP, n=30 after 1 warm-up). p50 / p95:

| q | bdc4c57 | service.py reverted to 838beea |
| --- | --- | --- |
| blender | 22.3 / 24.3 ms | 206.5 / 214.4 ms |
| blendr | 23.2 / 25.4 | 219.0 / 228.2 |
| power bank ultra | 53.5 / 60.6 | 344.6 / 372.0 |
| northwind (brand) | 48.6 / 51.5 | 225.9 / 230.7 |
| fabrikam (brand) | 41.3 / 48.7 | 220.1 / 236.7 |
| len (fragment) | 22.6 / 29.6 | 204.2 / 212.7 |
| zzzz (no hit) | 19.1 / 21.2 | 180.4 / 193.0 |

Every query is under the 300 ms read budget, and 4–10× faster than before. EXPLAIN of the statement the service sends:
the name and fragment lists are `Index Scan using products_i1_idx` (20 rows). The brand list is still
`Seq Scan on products rows=50004` whenever any brand matches (`blender` matches "AquaBlend"), 38–78 ms execution.
`products_i4_idx` is not used by the application. The LATERAL form database-engineer proposed takes 0.18–0.36 ms → **DEF-110**.

**Gates (all run here, on the restored tree):**
- backend `uv run ruff check .` → `All checks passed!` · `uv run pytest -q` → `149 passed, 4 warnings in 35.27s`
- schema `pytest db/tests --ignore=db/tests/test_performance.py` → `101 passed in 3.86s`
- `pytest db/tests/test_performance.py -s` → `14 passed in 61.36s`. New case "A brand's products in name order" 0.09 ms
  (`products_i4_idx`); "Fuzzy product search (trigram)" 16.31 ms (`products_i1_idx`).
- `cd frontend && npx tsc --noEmit` → 0 errors · `npm run build` → `✓ built in 3.63s`
- `make db-gen` → `git status` / `git diff` empty (byte-for-byte)
- e2e journey: not run. The brief did not ask for it, and another agent was using the shared stack on :4310.

### New defects
- **DEF-110** (S3, catalogue-engineer): the brand list of search still seq-scans `products` whenever a brand matches,
  and no test fails if search goes back to a full scan.
- **DEF-111** (S4, frontend-engineer): `pages/admin/AdminLayout.tsx` still says "Sign in to continue" when the API is
  unreachable, which DEF-100 fixed only in `Gate`.

### Nits
- `frontend/src/pages/ReviewQueue.tsx:23` says ``mine`` is "Not sent by the API yet (DEF-101)". It is sent now.
- DEF-081: no test shows that a *different* `IntegrityError` on register still raises. The mutation `if False:`
  (catch everything) leaves all 16 identity tests green.
- `Layout.tsx:185`: "Offline" is `text-muted` on the dark (scrolled/hero) header variant too; check the contrast. That
  file is tech-lead's.
- DEF-080's docstring in `_by_words` ("nothing reads the whole table") is not true until DEF-110 is fixed.

### Good
- The search keeps the old rank measure exactly (`<->>` = 1 − word_similarity), and the paging test across ties is a
  real guard: it caught my ordering mutation.
- `test_spec_indexes.py` turns "every FK has an index" into a standing rule with a named allow-list.

### Not checked
- DEF-100 and DEF-101 in a browser (code review and tsc only).
- The embedder-fusion path of search (no embedder configured; `CANDIDATES` path not timed).

Worktree left clean: HEAD bdc4c57, no diff, no commits. `frontend/node_modules` (symlink) was already untracked.
Build caches, `backend/.venv` and `frontend/dist` were removed. DB `qa_last_perf` was dropped.
