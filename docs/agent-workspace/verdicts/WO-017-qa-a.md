# WO-017 run 2 — QA part A: WO-001, 003, 006, 009, 011, 012 and DEF-005

qa-test-engineer · 2026-11-22 · worktree `../wt-qa-a` (branch `wt/qa-a`, from `week-02` @ `706b0f8`) · lane 1
(Postgres :55441, Redis :63841). Every mutation below was made in the worktree and reverted with `git checkout`;
each "restored" line is a re-run after that revert.

| WO | Verdict | One line |
|---|---|---|
| WO-001 | **PASS** (one finding: DEF-010) | All five behaviours hold and each has a test that fails on revert. The review → wallet-holder alert path was untested; a test is now added. Demo passports carry an uncited hazard component (DEF-010). |
| WO-003 | **PARTIAL** | The CPSC recall ingestion works, is tested and fails on revert. Marketplace products, the media hand-off and `ProductIngested` were never built (the WO says so). |
| WO-006 | **FAIL** — DEF-011 (S2), DEF-012 (S3) | Flags, corrections and holds work and are revert-proven. A moderator can release their own fraud hold, and `dismiss` leaves holds frozen and flags pending for good. |
| WO-009 | **PASS** | Run 44909379562 failed its e2e job and skipped the release. Run 44923886453 was green through `Check the live site`. The workflow uses no `secrets.*`. |
| WO-011 | **PARTIAL** | No Alembic. The enums match the spec exactly; the drift test fails on revert. db-test 66 passed. Phases 2–3 are still not migrations (named deviation) and DEF-007 is open. |
| WO-012 | **FAIL** — DEF-013 (S3), DEF-014 (S4) | Scan formats, UPC-E, tsc and build are fine. 56 literal colours in components, and a reload drops the "show more" depth. |
| DEF-005 | **CLOSE** | One schema; 61/61 enums identical to `schema_spec.py`; drift test guards it (revert proof under WO-011). |

## Gates (run by me, in the worktree, on lane 1)
- Backend at `706b0f8`: `ruff check .` → `All checks passed!`; `pytest -q` → `83 passed, 4 warnings in 21.04s`.
- Backend with my added test (commit `13c6827` on `wt/qa-a`): `All checks passed!`; `84 passed in 17.10s`.
- Schema: `pytest db/tests --ignore=db/tests/test_performance.py -q` → `66 passed in 3.56s`.
- Frontend: `npx tsc --noEmit` → no output (clean); `npm run build` → `✓ built in 5.87s` (chunk-size warning only).
  **Environment note:** the worktree's `frontend/node_modules` was a symlink to the main tree's, which is
  **stale** (54 packages; `lucide-react`, `motion`, `sonner`, `@zxing/*`, `canvas-confetti` missing). With it,
  tsc gave 52 errors (`TS2307 Cannot find module 'lucide-react'`…). I replaced the symlink with a private `npm ci` in the
  worktree. The main tree needs `cd frontend && npm ci` before anyone runs the frontend gate there.
- `npm run journey`: **not run**. It needs a `make dev` stack, which is browser-qa-engineer's lane in this run.

---

## WO-001 — Foundation
| Criterion | Result | Evidence |
|---|---|---|
| `alembic upgrade head` gives 90 tables | Superseded (Alembic removed by WO-011). The equivalent holds. | DB built from `db/migrations` + core seed + `db/schema-next` has 95 base tables: exactly the 94 in `schema_spec.TABLE_BY_NAME` plus PostGIS `spatial_ref_sys` (`comm -3` of the two lists → only `spatial_ref_sys`). Nit: `docs/database/schema-design.md:8` still says "90 tables". |
| Sign-up → codes → Level 1 → coins pending → confirmed by the coins handler | PASS (updated by ADR-006: email code only; 105 pending = 100 Level 1 + 5 daily sign-in) | `tests/test_journey.py:84 test_signup_to_coins`; handler `app/workers/handlers/coins.py:12` calls `rewards.confirm_due` → `coin_confirm_due()` (`app/modules/rewards/service.py:52`). |
| Review writes `ReviewSubmitted`; handler issues passport v+1; wallet holder gets an alert | PASS. The alert half had no test; **test added.** | Event emitted at `app/modules/community/router.py:106`; `tests/test_journey.py:148`. An alert goes out only when a risk event is new (business rules §5). For a review that is the hazard threshold (`app/modules/screening/service.py:345-348`, threshold 80). New `backend/tests/test_review_alert.py::test_a_review_over_the_alert_threshold_alerts_the_wallet_holder_once`: v+1, one `RiskEventRaised`, delivered twice → one alert, bystander none. |
| Reused refresh token revokes the family | PASS | `app/modules/identity/service.py:219-226`; `tests/test_journey.py:122`. |
| Recalled demo product reads `recalled` with the recall cited | PASS (with DEF-010) | Test catalogue: `tests/test_journey.py:241`. Real demo data (DB `qa_a_demo` built like `make app-db`, API on :4391): `acme-powerblend-1000` → `badge recalled tier 2 version 1`, `recall_matches [('match', 'Acme Kitchen PowerBlend 1000 Blenders Recalled Due to Laceration Hazard')]`, url `https://www.cpsc.gov/Recalls`. **But** every demo passport has `hazard_component 100.0` with `hazard None` → **DEF-010**. |

Revert proofs:
```
# coins: app/modules/rewards/service.py:52   return int(await db.scalar(text("select coin_confirm_due()")))  ->  return 0
FAILED tests/test_journey.py::test_signup_to_coins  {'confirmed': 0} != {'confirmed': 105}   1 failed
restored: 1 passed, 21 deselected in 2.00s

# re-screen: app/workers/handlers/screening.py  await screen_product(...)  ->  pass
tests/test_journey.py:170: assert after["version"] == before["version"] + 1   E assert 1 == (1 + 1)   1 failed
restored: 1 passed, 21 deselected in 2.48s

# alert threshold: app/modules/screening/service.py:346  total >= threshold  ->  total >= threshold + 1000
tests/test_review_alert.py:61: assert len(raised) == 1   E assert 0 == 1   1 failed in 5.96s
restored: 1 passed in 7.17s

# family revoke: app/modules/identity/service.py:222  SessionRow.family_id == row.family_id  ->  SessionRow.id == row.id
tests/test_journey.py:134: assert (await client.get(.../auth/me, headers=fresh)).status_code == 401   E assert 200 == 401   1 failed
restored: 1 passed, 21 deselected in 2.56s

# recall cited: app/modules/screening/scorer.py  "safety.regulatory": ("recall", ...)  ->  without "recall"
tests/test_journey.py:246: assert regulatory["citations"] and ...[0]["kind"] == "recall"   E assert ([])   1 failed
restored: 1 passed, 21 deselected in 2.17s
```
(A first attempt that renamed the emitted event to `ReviewSubmittedX` failed only with "unrouted event type", which proves nothing.
It was replaced by the handler mutation above.)
Not checked: the `/auth/me` race fixed with `scope="function"` (the WO says no test reproduces it); the default
`JWT_SECRET` refusal outside local (the WO says it has no test). **Verdict: PASS.** DEF-010 is filed against the seed, not this WO's code.

## WO-003 — Ingestion
No `## Acceptance` section. I checked against its scope and log.
| Item | Result | Evidence |
|---|---|---|
| `POST /ingest`, `GET /jobs`, `GET /jobs/{id}` admin-only; `GET /recalls` public | PASS | `app/modules/ingestion/router.py:16`. Live on :4391: no token → `POST /ingest 401`, `GET /jobs 401`, `GET /jobs/{id} 401`; Level-1 member → `403` on all three; `GET /recalls 200`. Test covers member/moderator 403 (`tests/test_ingestion.py:65`). No test asserts the 401s (gap, nit). |
| Raw copy kept once by SHA-256; unchanged stops; changed replaces without duplicates | PASS | `app/modules/ingestion/service.py:161-170`; `tests/test_ingestion.py:76` |
| A recall naming a registry product triggers its re-screen → `recalled` | PASS | `service.py:179-180` emits `RecallImported`; same test |
| A bad record does not lose the rest; an unreachable source fails visibly | PASS | `tests/test_ingestion.py:127`, `:139` |
| Contract test on a recorded response | PASS | `tests/fixtures/cpsc_recalls.json` |
| Nightly 03:00 UTC sync | Present, untested | `app/workers/main.py:57` |
| Marketplace product ingestion, match-or-create products, media hand-off, `ProductIngested` | **Not built** | WO log says so (sources declined) |

Revert proofs:
```
# hash: service.py:168  SourceRecord.payload_sha256 == digest  ->  == digest + b"x"
assert await run_job(again["id"], ...) == {...}   {'unchanged': 0} != {'unchanged': 3}; {'errors': 3} != {'errors': 0}   failed
restored: 1 passed, 7 deselected in 2.82s
# role: router.py:16  require_role("admin")  ->  require_role("admin", "moderator")
FAILED tests/test_ingestion.py::test_only_an_admin_starts_a_job - assert 202 == 403
restored: 1 passed, 7 deselected in 2.79s
```
**Verdict: PARTIAL.** The CPSC recall source is verified. Products are still not created from any outside
source, so M1's "creates products without typing" is not met here.

## WO-006 — Safety-team queue
| Item | Result | Evidence |
|---|---|---|
| Confirm a flag → `confirmed`, 25 coins, trust +2, alert, re-screen cites it | PASS | `tests/test_moderation.py:32` |
| Reject a flag → no coins, trust −1 | PASS | `tests/test_moderation.py:78` |
| Accepted correction changes the product, pays once per product | PASS | `tests/test_moderation.py:104` |
| Fraud hold released through `coin_resolve_hold` | PASS (release only; "confirm fraud" has no test) | `tests/test_moderation.py:133` |
| Staff cannot decide their own contribution | **FAIL for fraud holds** | Flag `service.py:113`, fact `:145`; fraud hold `:192-194` has no check. Probe: moderator's own hold, `reject` → `RESOLVE 200`, frozen 105 → confirmed 105. **DEF-011 (S2)** |
| Queue is staff-only | PASS | no token `GET /review-tasks 401`; member `GET 403`, `POST .../resolve 403` (live, :4391); `tests/test_journey.py:233` |
| `dismiss` | **FAIL** | `service.py:187` skips the subject: hold stays frozen, flag stays pending (reporter then gets `409 flag_pending` forever). **DEF-012 (S3)** |

Revert proofs:
```
# own flag: service.py:113  if flag.reporter_user_id == staff.id:  ->  if False:
tests/test_moderation.py:101  E assert (200 == 409)   1 failed;   restored: 1 passed, 4 deselected in 4.00s
# pays: service.py:125-127  rewards.earn(... "hazard_flag_confirmed" ...)  ->  skipped
tests/test_moderation.py:60  E assert [] == [25]   1 failed;   restored: 1 passed, 4 deselected in 3.82s
# hold: service.py:193  "is_fraud": confirm  ->  "is_fraud": not confirm
tests/test_moderation.py:153  E assert (0, 0) == (105, 0)   1 failed;   restored: 1 passed, 4 deselected in 2.29s
```
Ownership note: `backend/app/modules/moderation/**` is not in `telcron-domain-map`. I routed both defects to
WO-006's owner (community-rewards-engineer); tech-lead should confirm and add the row. **Verdict: FAIL** (DEF-011, DEF-012).

## WO-009 — Pipeline
| Criterion | Result | Evidence |
|---|---|---|
| A failing push does not release | PASS | `pipeline.yml` `release.needs: [deps, schema, backend, frontend, e2e]`. Run **44909379562** (main `4f522a3`): `End-to-end journey -> failure`, `Release to dev -> skipped`; `4f522a3` is in no `release/dev` commit message (`grep -c` → 0). |
| Green push to main goes live without touching AWS, and the run checks the live site | PASS | Run **44923886453** (main `23f8769`): all jobs success. Release steps: `Publish the release -> success`, `Wait for both hosts to deploy it -> success`, `Check the live site -> success`. `origin/release/dev` head `79a5ec7 Release 23f87692b21c` = `origin/main` `23f8769`. |
| The workflow holds no cloud credentials | PASS | `grep -n "secrets\.\|aws-actions\|AWS_\|id-token" pipeline.yml` → no match (exit 1). Only `github.token` (release job, `contents: write`) and `vars.DEV_*`. |

`gh` is not installed on this machine. The same read-only data came from the public GitHub REST API
(`/actions/workflows/pipeline.yml/runs`, `/actions/runs/{id}/jobs`). No push, no dispatch, no AWS.
The last 12 runs on main: 11 success, 1 failure (the one above).
Notes, not blocking:
- `week-02` adds a `deps` job (`tools/dependency-scan.sh`, from the unreviewed WO-020 merge) that the release needs.
  It has not run on GitHub yet and is reviewed under WO-020.
- `release/dev` is unprotected (already stated in the WO).
- A revert proof does not apply: the evidence is a real red run that skipped the release.
**Verdict: PASS.**

## WO-011 — Converge on the designed schema
| Criterion | Result | Evidence |
|---|---|---|
| Backend tests pass against a DB from the dbmate migrations **only** | PARTIAL | They pass (`83 passed`), but on migrations + `001_core_reference.sql` + `db/schema-next/*` (`tests/conftest.py:46-50`). Phases 2–3 are not migrations (named deviation in the WO). |
| `make db-test` passes | PASS | `66 passed in 3.56s` |
| No Alembic; no enum value in `enums.py` that the spec lacks | PASS | `ls backend/alembic backend/alembic.ini` → No such file; no `alembic` in backend sources. Independent script, `app.models.enums` vs `schema_spec.ENUMS`: `code enums 61 spec enums 61 values in code not in spec: {} types not in spec: []`, `order/value mismatches: []`. |
| DEF-001, DEF-003 closed or re-filed | PASS | DEF-001 `RESOLVED`, DEF-003 `CLOSED`. DEF-007 (raised by this WO) still `OPEN`. |
| Coins only through `coin_*` | PASS | No `insert/update/delete` on `coin_ledger_entries`/`coin_balances` in `backend/app` (only `seed.py:44` updates `coin_earn_rules` config locally). Calls: `coin_earn`, `coin_confirm_due`, `coin_redeem`, `coin_resolve_hold`, `coin_history`. Ledger append-only: `tests/test_journey.py:114`. |

Revert proof (drift):
```
# enums.py  user_role = _e("user_role", "user", "moderator", "admin")  -> + "safety_reviewer"
tests/test_schema_drift.py:105  AssertionError: enum user_role: ['user', 'moderator', 'admin', 'safety_reviewer'] here, ['user', 'moderator', 'admin'] there   1 failed
restored: 1 passed in 1.58s
```
**Verdict: PARTIAL.** The convergence is real and guarded. Not done as written: phases 2–3 promoted to migrations; DEF-007 open.

## WO-012 — Web app redesign
| Criterion | Result | Evidence |
|---|---|---|
| Every page renders at 390 px and desktop, no console error | Not checked by me | browser-qa-engineer's lane this run |
| Tokens only (no literal colours) | **FAIL** | 49 Tailwind-palette classes + 7 hex/`rgb()` in `frontend/src/**/*.tsx` (e.g. `components/ui.tsx:100-113`, `pages/Rewards.tsx:147` confetti hex). **DEF-013 (S3)** |
| Camera scan reads EAN-13, UPC-A, UPC-E; QR ignored | PASS (code + backend test; no camera used) | `pages/Scan.tsx:16-17`: `POSSIBLE_FORMATS = [EAN_13, EAN_8, UPC_A, UPC_E]`, so the QR reader is never tried. UPC-E expansion: `backend/app/modules/catalogue/identify.py:48-75`; `tests/test_identify.py:15`. |
| Search and lists paginate; reload keeps the page | Paginate PASS; reload **FAIL** | `lib/usePaged.ts:24` always loads offset 0; the depth is not in the URL. Query kept (`Search.tsx:11`). Backend paging `tests/test_journey.py:272`. **DEF-014 (S4)** |
| tsc, build, journey | tsc PASS, build PASS, journey **not run** (browser lane) | see Gates |

Revert proof (UPC-E):
```
# identify.py  body = x[0:2] + last + "0000" + x[2:5]  ->  x[0:2] + "0000" + last + x[2:5]
tests/test_identify.py:21  AssertionError: assert '042000015264' == '042100005264'   1 failed
restored: 1 passed, 12 deselected in 1.72s
```
**Verdict: FAIL** (DEF-013, DEF-014).

## DEF-005 — Two schemas; wrong enum values
The fix is WO-011. There is one schema, generated from `docs/database/schema_spec.py`. The backend maps onto it:
61/61 enum types identical in names, values and order. The drift test is green and goes red on a wrong value
(proof above). The backend's coin writes go through `coin_*`. **Verdict: CLOSE.** The remaining gap (phases 2–3 not
promoted to migrations) belongs to WO-011 and DEF-007, not this defect.

## Added test
`backend/tests/test_review_alert.py`, committed on `wt/qa-a` as `13c6827`
("WO-017 QA: a review over the hazard alert threshold alerts the wallet holder once"). It stands in for the
model with a scorer class (a provider replaced wholesale, as `test_llm_scorer.py` does) and adds its own
product through `/identify/confirm`, so it shares no state with other tests.

## Flagged, not filed
- The main tree's `frontend/node_modules` is stale (see Gates). `npm ci` is needed there.
- `docs/database/schema-design.md:8` says 90 tables; the spec has 94.
- `POST /auth/register` on a stack with no mail settings answered `"email_sent": true` (on :4391, `ENV=test`).
  WO-013 is security's. Mentioned only in case it is not deliberate.
- No 401 tests for the ingestion routes; no test for `fraud_hold` "confirm"; no test for `dismiss`.

## Clean-up
All mutations reverted (`git checkout` after each). `git -C ../wt-qa-a status --short` → empty after the commit.
Throwaway DB `qa_a_demo` on lane 1 dropped; the uvicorn on :4391 was started with `timeout 300` and has exited.
