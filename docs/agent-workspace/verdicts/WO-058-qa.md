# WO-058: QA verdict (backend, schema, gates, DEF-121 isolation)

qa-test-engineer · 2026-11-23 · branch `week-02` @ 80f18b2 (commits b943aab..HEAD), local only, nothing pushed.
Shared stack: API :4310, Worker and web :3200, started 17:14:13. That is after the last backend commit (c85d649,
17:01:40), so it serves the new code. I deleted the 4 `telcron:passport:*` keys in Redis db 0 before the API checks.

## Verdict: APPROVE WITH NITS
I checked every backend and schema acceptance line of WO-058 and every section of CT-003 (§A to §E) against the
code and against the running API. All pass. Each key test went red under my own revert and was restored, and
`git status` shows no tracked change. The e2e journey ran on a disposable database. It left the shared database
row-for-row identical and left nothing running. The two order-dependent test failures that lanes reported are
real and older than WO-058 (they fail the same way at b943aab), so I filed them as **DEF-122** (S3, data-ai-engineer).
They do not block. The visible frontend items passed a code reading only; browser-qa-engineer gives the verdict on
how they look and behave in the browser.

## Gates (I ran each one)
| Gate | Result |
| --- | --- |
| `make api-test` | ruff `All checks passed!` · `175 passed, 4 warnings in 33.78s` (the warnings are Starlette's existing HTTP_422 deprecation) |
| `make db-test` | `106 passed in 3.94s` |
| `cd frontend && npx tsc --noEmit` | exit 0, no output |
| `npm run build` | `✓ built in 3.69s` (the >500 kB chunk warning was already there) |
| `cd e2e && PW_CHANNEL=chromium npm run journey` | `database telcron_e2e_1795434420_208940` · `9 passed (56.1s)` · `removed: processes 209334 209335 209336 209384, Redis index 9, database telcron_e2e_1795434420_208940` |
| What the journey left behind | `telcron_e2e_*` databases: 0 · Redis index 9 `dbsize` 0 · ports 4311 and 3201 free · `docker ps -a --filter name=tc-lane`: empty |

## Per defect
| Defect | Verdict | Evidence |
| --- | --- | --- |
| DEF-113 (corpus date) | PASS | `screening/service.py` `CORPUS_DATE` = max `finished_at` ≤ now of a `succeeded`/`partial` CPSC job, or of a research run with `stats.sources.cpsc = 'answered'`. It falls back to `now` only when no such job exists. `test_corpus_date.py` covers newer failed jobs, a research run with cpsc failed, legacy runs and a job finishing in the future. |
| DEF-113 (`recall_checked_as_of`, CT-003 §A) | PASS | Live: all 13 current passports return the key. Each value equals `screenings.corpus_synced_at` of `passports.screening_id` to the microsecond (e.g. acme `2026-11-23T10:54:52.750991+00:00`). Every current passport in the shared DB has a screening, so I checked the `null` branch in `test_passport_view.py` (tier-1 passport with no screening gives `null`), not live. The CT-002 report reuses `passport_view` (`test_report_access.py` green). |
| DEF-113 (verdict copy) | PASS (code) | `components/Verdict.tsx:16-22`: a total ≥ 60 or any scored dimension ≥ 60 is "serious", 30 to 59 is "some". Both warn and point to the hazard scores. "checks passed" appears only when the level is `none` and the badge is `verified`. `recallAsOf` gives "as of the last check" for null, absent or invalid dates. The report uses the same `shownRecalls` filter. |
| DEF-114 | PASS (code) | `pages/Product.tsx:120,150-157`: "Where to buy" is not rendered while the passport loads or when there is a `match`. A `near_match` shows a warning inside the menu. |
| DEF-115 (`stats.sources`, CT-003 §B) | PASS | Live: every existing run is from before this change, so `stats` has no `sources` key, as §B requires for legacy runs, and `errors` is codes only (`["web"]`). `web.NotConfigured` is a subclass of `ResearchUnavailable`, raised for a missing search key and a missing model key. Tests: no provider gives `web: not_configured`, `reader: not_configured`, `pages == 1`. Provider errors give `failed`, and the provider text is not in the response. Copy in `components/Research.tsx:113-118` (code). |
| DEF-116 | PASS (code) | `Reviews.tsx:123` starts the rating at 0. `role="radiogroup"` is present. `ui.tsx:144` gives a shown rating `role="img"` and `aria-label`. |
| DEF-118 (CT-003 §D) | PASS | Live `GET /rewards` as a Level-1 member: `level1_verified` "Verify your email" 100 available. `login_streak` "Sign in each day" 5. `login_streak_7plus` "Sign in each day from day 7 of a streak" 10. `photo`, `referral` and `level2_verified` are `available=False`. Every other earn is `True` and no amount changed. Frontend (code): "Coming soon", "From N coins earned in total", "+1 555 010 0123", and Gate.tsx says "Confirm your email first". |
| DEF-119 | PASS (code) | `Report.tsx:37` and `Product.tsx:274` link to `/rewards?product=<slug>`. The e2e journey asserts the pre-selection and the redemption (tests 5 and 6 passed). CT-002 routes are unchanged. |
| DEF-120 (CT-003 §C) | PASS | Live `GET /review-tasks` as admin lists 12 missing-evidence tasks. Each has `missing_dimensions` with names (e.g. acme: Environmental Harm, Regional Constraints, Animal Harm) and a `passport_version` (5, 13, 12, 2…). The 2 pre-DEF-032 tasks show `[]`. The `hazard_flag` task gained no new keys. Shared DB: at most 1 open task per product, 12 open, 8 dismissed with the `superseded:` note, and migration `20261123120000` applied. Queue and data-sources copy in `ReviewQueue.tsx:86-88` and `DataSources.tsx:56-66` (code). |
| DEF-121 (journey isolation) | PASS | Shared DB before and after my journey run, identical by `diff`: e2e members 30 (newest still 2026-11-22 17:49:20), users 44, Lumina products 9, products 13, Northwind reviews 11, reviews 15, flags 12, wallet items 19, redemptions 7, review tasks 36, passports 51. CI: `pipeline.yml:109-111` still runs `working-directory: e2e` / `npm run journey`. With `CI` set, `disposable-journey.sh:17` runs `exec npx playwright test journey "$@"` (`CI=true npm run journey -- --list` gives `Total: 9 tests in 1 file` and starts nothing). |
| DEF-121 (CT-003 §E) | PASS | Live: the default list has 13 products, `screened=true` has 3 (contoso, northwind, acme; all tier 2), and `screened=false` gives the same list as the default (`True`). `q=lumina` matches 9 products, none screened. `screened=maybe` gives 422. Pages continue: `limit=2` gives [contoso, northwind] and `offset=2` gives [acme]. The order is created_at desc, then id desc, because all three share one created_at. `Home.tsx:35` calls `/products?limit=6&screened=true`. |
| Access unchanged | PASS | Live: `/review-tasks` without a token is 401, as a member 403, as admin 200. `/rewards` without a token is 401, with a bad token 401, as a member 200. `git diff b943aab..HEAD -- backend/app/core backend/app/modules/identity backend/app/modules/moderation/router.py` is empty. The rewards dependency is still `Level1User`. A Level-0 session cannot be obtained over HTTP (sign-in refuses an unverified email), so the existing tests cover the 403 for Level 0. |
| DEF-117 | not verified | Out of scope: it waits on the human. |

## Revert proofs (each one my own mutation, red, then restored with `git checkout --`)
| # | File: mutation | Result |
| --- | --- | --- |
| 1 | `research/web.py`: `raise NotConfigured("no search provider configured")` changed to `raise ResearchUnavailable(...)` | `test_with_no_search_provider_the_web_is_not_configured_and_not_counted` failed: `{'web': 'failed'} != {'web': 'not_configured'}` · `1 failed, 4 passed` |
| 2 | `screening/service.py`: `corpus = ... or now` changed to `corpus = now` | `test_a_screening_records_the_newest_successful_cpsc_import` failed · `1 failed, 1 passed` |
| 3 | `screening/service.py`: `status IN ('succeeded','partial')` with `'failed'` added | the same test failed · `1 failed, 1 passed` |
| 4 | `rewards/router.py`: `UNAVAILABLE = frozenset()` | `test_ways_to_earn_follow_d4_and_mark_unavailable_earns` failed · `1 failed` |
| 5 | `catalogue/service.py` `_screened`: `if not only:` changed to `if True:` (filter off) | `test_screened_leaves_out_products_without_a_tier_2_passport` and `test_the_route_takes_screened_and_needs_no_account` failed · `2 failed, 1 passed` |
| 6 | `catalogue/service.py`: `checked_as_of = None` | `test_the_passport_states_the_corpus_date_of_its_screening` failed · `1 failed, 1 passed` |
| 7 | `moderation/service.py`: `subject \|= missing.subject(task)` changed to `pass` | `test_a_missing_evidence_task_names_its_dimensions_and_passport` failed · `1 failed, 1 passed` |
| 8 | migration `20261123120000`: `ORDER BY created_at ASC, id ASC` (keeps the oldest) | `make db-test`: `1 failed, 105 passed` (`test_only_the_newest_open_missing_evidence_task_of_a_product_stays_open`) |
| 9 | migration `20261123120000`: `r.rn > 99` (dismisses nothing) | `make db-test`: `1 failed, 105 passed` (same test) |

After all nine: `git status --short` shows only `?? docs/database/db_erds.zip` (the human's untracked file, there
before I started), plus my two new files under `docs/agent-workspace/`. I committed no mutation. Each mutation
was on disk only for the few seconds its targeted test took.

## Pre-existing test-order failures → DEF-122
| Order | HEAD 80f18b2 | b943aab (temporary worktree, removed) |
| --- | --- | --- |
| `test_moderation.py test_insufficient_data_task.py test_journey.py` | `1 failed, 34 passed`: `assert 6 == (2 + 1)` | `1 failed, 34 passed`: same assertion |
| `test_research.py test_ingestion.py` | `1 failed, 30 passed`: `products_rescreened` 2 != 1 | `1 failed, 30 passed`: same |
| full default order | `175 passed` | `160 passed` |

Both fail before WO-058, so they are real and not a regression. Filed as `defects/DEF-122.md`, owner data-ai-engineer,
with a likely mechanism for the first: a stale `telcron:passport:*` cache key after a direct `screen_product` call
in a test. Worktree removed: `git worktree list` shows only the main tree.

## Nits (non-blocking)
1. Every screening in the shared DB is older than the corpus-date fix, so its `corpus_synced_at` is the
   screening's own clock. The passport therefore says "as of <screening time>" until each product is re-screened.
   This is true to the data, but it is not yet the corpus date. New screenings are correct.
2. The `screened=true` filter on the meaning (embedding) search path has no test (lane B says so). It is correct
   by reading (`catalogue/service.py` filters the fused ids before the cut).
3. On this machine the journey needs `PW_CHANNEL=chromium` (the headless-shell build is missing; lane F flagged
   it). CI is unaffected.
4. `CORPUS_DATE` filters `web_search` jobs on JSONB with no supporting index. That is fine at today's volume.
   Lane A flagged it, and nobody has measured it.

## Not done
- No browser walk-through of the visible items: that is browser-qa-engineer's gate. The frontend items above
  are PASS (code) only.
- I did not exercise a new research run or a new screening on the shared stack (both would write to the shared
  DB). The integration tests above cover them, and each has a revert proof.
- I did not edit WO-058.md (another verifier is working on it).
