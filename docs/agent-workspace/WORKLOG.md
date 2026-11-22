# Worklog

Append-only. Written by `worklog-scribe`. Newest entry last.

## 2026-11-15 — Foundation run (WO-001), AWS dev account, first push

**Decided by the user**
- Stack: React frontend, FastAPI backend. A TypeScript start made earlier the same day was deleted.
- UI follows testlabhub.com.
- Repository: first a private one under a personal account was chosen; later the user named
  `CodeGang007/telcron`, confirmed that its being public is fine, and said to push to `main`.
- AWS: Lightsail for the frontend, the smallest EC2 for the backend, PostgreSQL, Redis in Docker on the
  EC2 host. Target cost USD 20 to 22 a month.

**Built** — see WO-001 for the detail and the gate output.

**Found at push time**
- `CodeGang007/telcron` already had a branch, `feat/database-schema`, with the designed database:
  `schema_spec.py`, dbmate migrations, database-enforced rules, tests. The backend's schema had been
  built from the ERD pictures without it. Tables and columns match by name; 54 of 61 enum types have
  different values. Filed DEF-005 and WO-011. That branch was not touched or merged.
- That branch's `CLAUDE.md` says source documents live outside the repository. The local copies were
  therefore kept out of git (`docs/reference/`, gitignored).
- Because the repository is public: the seeded admin's password was moved out of the code into
  `SEED_ADMIN_PASSWORD`, the API now refuses the default `JWT_SECRET` outside local, and AWS
  identifiers are kept in a gitignored file.

**AWS dev, us-east-2** — inventory, cost and gaps in `docs/runbooks/aws-dev.md`. Created through
CloudShell in the console; no access keys were made. Four "Earn AWS credits" activities showed as
completed; the resources made only for them were deleted afterwards. The Bedrock activity could not be
done: the account's quota is zero.

**Open** — eleven work orders and six defects on the board; three decisions waiting on the human.

## 2026-11-15 — Converged on the designed schema (WO-011)

**Decided by the user**
- Rework the backend onto the schema of `feat/database-schema` on a new branch, for review.
- The AWS dev environment stays as built, about USD 33 a month ("its fine actually").
- Other local projects' dev servers were to be closed; Osten's were stopped with its own script.

**Done** on branch `feat/backend-on-designed-schema` — see WO-011 and ADR-005. The backend now creates
nothing: it maps the designed schema and a drift test guards the mapping. The database's rules replaced
the Python duplicates. Three faults surfaced and were fixed.

**Not done** — phases 2–3 are still not migrations; DEF-007 lists three gaps for the schema's author; the
two remaining "Earn AWS credits" activities (the browser chosen for it was not signed in to AWS).

## 2026-11-15 — Merged into main

At the user's instruction ("merge to main now") `feat/backend-on-designed-schema` was fast-forwarded into
`main`. That landed `feat/database-schema` as well. No pull request was opened; the schema's author has not
reviewed the convergence.


## 2026-11-16 — Deployed to AWS dev; pipeline through main (WO-002, WO-009)

**Decided by the user**
- Deploy to AWS. Sign-up stays closed on the deployed site, with one seeded admin, until codes can be sent.
- Yes to: HTTPS on wildcard-DNS hostnames with Let's Encrypt; generated passwords in the app secret; the
  instance role reading the RDS master secret; fixed addresses; pushing the deploy files to `main`.
- Everything tested end to end, and an end-to-end CI/CD pipeline through `main`.
- The AWS CLI was installed for the user (no sudo); the user signed in with `aws login`. No keys exist.

**Done** — the dev site is live (WO-002). A push to `main` is tested and, if green, released to it without
anyone touching AWS (WO-009). The pipeline is pull-based because the account's policy denies the identity
provider GitHub would need; nothing was done to get around that.

**Not done** — security review of the deployment; DEF-006; the branch `release/dev` is unprotected; two
"Earn AWS credits" activities; everything else on the board.

Gates, 2026-11-16: pipeline run 43751927320 for commit f267b07 succeeded in all five jobs (schema tests, backend lint and tests, web typecheck and build, the member's journey in a browser, release to dev). After it both hosts reported f267b07 as the running build, without anyone touching AWS. Against the live site: the read-only smoke set passed 5 of 5, and the member journey signed in as the admin passed 5 of 5 steps (wallet round trip, a review re-screened from passport v1 to v2, earlier coins confirmed). Locally: make db-test 66 passed, make api-test 26 passed, journey 4 passed.


## 2026-11-21 — Moderation, recalls ingestion, scanning, AI scorer, evals, redesign

**Decided by the user**: stay on the AWS Free plan (so no Bedrock); no SerpApi/ScraperAPI, use free sources;
use a free model ("something like grok"): Groq's free plan chosen, not xAI (no free tier); redesign the UI with
open-source components, animation, logos, pagination; everything working end to end.

**Live** (commit c921389, all through the pipeline): safety-team review queue; CPSC recall ingestion (nightly +
admin) with 132 real notices imported on the dev site; barcode identification via UPCitemdb's free tier;
daily streaks, badges, coin store; the model scorer with stub fallback (switched off until a key exists);
`backend/evals` (12 cases) gating the pipeline at 90%; the redesigned web app.

**Found in Chrome, fixed**: newer Chrome returns a promise from `window.scrollTo`; an effect returned it and
crashed the app on every route change. The headless test browser did not have that behaviour, so the
pipeline did not catch it; the redesign build was live with it for one release (about 15 minutes).

**Honest caveat on evals**: the cases were written and the keyword placeholder tuned in the same session, so
its 97% is a regression baseline, not an independent quality measure.

**Open**: a Groq key to switch the AI scorer on; photo identification; media uploads; Level 2 identity; email/SMS
codes (sign-up still closed on the dev site).


## 2026-11-22 — W1–W2 completion, run 2 (branch `week-02`, `8363c82`..`7e1efd5`)

**Verified (WO-017, by agents other than the builders).** QA A and B, security, browser QA, a final gate on
`838beea` and a last re-check on `bdc4c57` (verdicts in `docs/agent-workspace/verdicts/WO-017-*.md`). Week-1
rows: WO-001, 009, 013, 014, 015 PASS; WO-002 and 016 PASS repo-only (nothing checked on the AWS hosts);
WO-003 and WO-004 PARTIAL (marketplace sources to WO-003b; scorer is Groq with stub fallback); WO-011 PARTIAL
(phases 2-3 now WO-022; DEF-007; schema author's review D14 still owed); WO-005 SUPERSEDED; WO-007/008/010 N/A.
WO-006 and WO-012 failed first (DEF-011 S2, DEF-012, DEF-013, DEF-014); the fixes passed QA. WO-018 and WO-024
failed first (DEF-021, DEF-020); both fixes re-checked PASS. Security: 0 Critical, 0 High, 6 Medium, 9 Low,
2 Info; its re-review (S-18..S-21) also passed. Last re-check: QA APPROVE WITH NITS, browser all PASS,
`npm run journey` 8 passed. Nothing is DONE; every row is DONE-PENDING-QA or lower.

**Fixed (all FIXED-PENDING-QA; QA PASS in the sweep unless noted).** DEF-010, 011, 012, 013, 014, 020, 021, 022,
023, 030, 031, 032, 033, 034, 036, 037, 038, 041, 042, 043, 044 (incl. infra: uvicorn no longer trusts
X-Forwarded-For; S-19 network), 048, 049, 060, 070, 080 (trigram KNN search and index `products(brand_id,
canonical_name, id)`, test that every foreign key has a serving index), 081, 100, 101. Runbook parts of DEF-040,
046, 047 passed. S-18 (rolling back a promoted migration is refused), S-20 (self-review falls back to the
submitter), S-21 (typed research quota) passed. DEF-090 (board vs file status lines) is closed by this entry's
board repair; QA has not re-checked it.

**Built.** WO-019 schema `e49911f` + service `2f40ce3` (redemptions: two items on sale, stuck ones refunded;
QA and security PASS). WO-020 dependency scan finished (fails closed on High/unrated; QA PASS). WO-022 phases 2-3
as dbmate migrations `41bdc29`; `db-next` retired. WO-023 traceability `d6dc9a9`. WO-054 raw copies to S3
(code only, off by default; PARTIAL). WO-055 admin shell and WO-056 feature flags (CT-001) with the web hook.
WO-057 evals at 20 cases (regression baseline only; offline harness, no live-model run).

**Decided (tech-lead; the human's decisions are listed below).**
- WO-054 departure accepted: the schema (`source_records_chk1`, exactly one of `payload` / `payload_storage_key`;
  rows immutable) is the rule, so on a successful upload the row holds the key only, otherwise the payload stays
  in the database. No schema change.
- Gap calls (agree with WO-023): audit log -> W3 WO-026; first marketplace -> W3 WO-003b; independent eval
  set -> W6 WO-038; member-photo safety DEF-024 -> W4 WO-007.
- M1 "scraping job" = CPSC official API (OP-20, human).

**Waits on the human.** Push `week-02` to `main`; DEF-040 key rotation; WO-021 sign-up on dev; DEF-006 items 1, 2,
4; DEF-045 DB owner role; DEF-047 backups; WO-054 enabling on dev; DEF-035 reading; DEF-046/S-7r ADR. Detail in
`RESUME-HERE.md`.

**Open.** DEF-035 decision (D13 reading a or b); DEF-110 (S3: brand list still reads every product when a brand
matches; fix with a LATERAL query on the brand path, plus a plan test; search is already under 300 ms);
DEF-111 (S4: admin area tells staff to sign in when the API is unreachable); DEF-007 (item 1 -> WO-029);
DEF-002 (D6; blocks WO-008); DEF-024 (W4); D14 review by the schema's author; ADR on Gemini data-sharing;
S-7r ADR (region/secret names); a partial unique index for DEF-032 (database-engineer); `tools/dev-all.sh` needs
`--no-proxy-headers` since DEF-044; the Playwright headless browser is not installed locally (browser QA used
what was available); `.env.local` points the database at port 5436.

**Not done.** Jira not updated (project-manager not dispatched, by instruction). Nothing was pushed; nothing on
AWS was changed or checked live. `docs/database/db_erds.zip` is untracked and untouched.

**Clean-up.** Every `tc-lane*` container and every QA/work worktree removed; `wip/wo-020-dependency-scan` is
merged and left in place.

## 2026-11-22 — DEF-035 fixed locally: the hazard report is gated (CT-002)

**Decided by the human.** Reading (a) of D13: gate the printable hazard report behind a fulfilled redemption.
The human accepted the residual risk below.

**Decided by tech-lead.** CT-002 frozen: `GET /api/v1/products/{id_or_slug}/report`. 401 for a visitor (checked
first), 404 `product_not_found` for an unknown product, 403 `report_not_redeemed` when the caller holds no
fulfilled `pdf_report` redemption for that product, 200 `{product, passport, redemption}` with
`Cache-Control: private, no-store`. Why 403 and not 404: the 404-for-another-user's-row rule exists so a response
never reveals another user's row. Here the URL names a public product, and the answer is identical whether nobody
or another member bought the report, so nothing about any other user leaks. The distinct code lets the web app say
"Redeem for 50 TelCoins to unlock" instead of "not found". The store item keeps its code `hazard_report_pdf` and
fulfilment type `pdf_report`; only its label changed.

**Commits (all on `week-02`, none pushed).** `37ac599` CT-002 and owners' reports in WO-019; `39c66ed` web
(Report.tsx reads only the gated endpoint; unlock card); `5bef64e` API (route and entitlement query);
`e6c75cc` migration relabelling the item "Full hazard report (printable)"; `76f2418` QA tests; `9c2357d` e2e
(flag evidence read from the free passport; new redeem-then-open journey); `e9143a8` DEF-112 filed; `5464976`
verdicts and board.

**Verdicts.**
- QA PASS (approve with nits): `make api-test` 160 passed, `make db-test` 103 passed, tsc 0, build ok. Revert
  proofs: router 403 removed, 6 failed; `user_id` filter removed, 5 failed; `status = 'fulfilled'` filter removed,
  2 failed; `fulfilment_type` filter removed, owner suite stayed green (gap), 1 failed with the QA watchlist test;
  label migration emptied, 2 failed.
- Browser PASS at 390 and 1280 px: visitor and non-redeemer see the unlock card, buyer sees the report and it
  survives reload, unknown product is not found for a member. `npm run journey` cannot launch a browser here; with
  a temporary `channel: 'chromium'` config (deleted) it gave 7 passed, 2 skipped.
- Security PASS-WITH-FINDINGS: no S1-S3. Static review only; no tests run by the auditor.

**Residual risk accepted by the human.** The 200 body equals the public product and passport reads, so the 50
coins buy a gated print layout of public data, not access to data. Store copy and support answers must not claim
otherwise.

**Open.**
- DEF-112 (S4): a visitor on an unknown product's report gets the unlock card (401 precedes the lookup).
- Security S4: `Report.tsx` does not `encodeURIComponent` the slug (pre-existing pattern); after sign-out the
  rendered report stays until navigation (data is public).
- `REPORT_COST = 50` is hard-coded in `Report.tsx` and duplicates the seed.
- Sign-in has no return path, so "Sign in" from the unlock card does not come back to the report.
- No test for `passport: null`.
- Rewards store card shows "Save a product..." copy while the wallet is loading.
- Playwright headless shell is not installed locally; installing it needs the human's OK.
- Parallel `make api-test` runs share `telcron_api_test` and collide (seen several times this run); needs a per-run
  database name (tech-lead/qa).
- `SEED_ADMIN_PASSWORD` unset locally, so journeys 6 and 7 skip.

**State.** DEF-035 is FIXED-PENDING-QA on the board, as is. Nothing pushed; Jira not touched. E2E members and two
redemptions remain in the local dev database (append-only ledger, by design). `docs/database/db_erds.zip` is
still untracked and untouched.
