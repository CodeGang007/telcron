# WO-017 run 2: browser verdict

## Browser QA: WO-017
Environment: local · branch `week-02` @ `706b0f8` · 2026-11-22 · Personas: visitor, member L1 (two), admin (safety team + data sources)
Agent: browser-qa-engineer · DEFs filed: DEF-030 … DEF-038

### Setup (what was run, so the run can be repeated)
- `make app-db` → `admin: admin@telcron.example.com` · `coin delay: 15s`; then `make dev` (API :4310, Worker, web :3200),
  `/health` → `{"status":"ok","version":"dev"}`; Worker log `Starting worker for 1 functions: handle`.
- Settings were exported in the shell for this run only. Nothing in `.env` changed: `SEED_ADMIN_PASSWORD` (generated, kept
  in the agent's scratchpad), `COIN_CONFIRM_DELAY_SECONDS=15`, `DEV_EXPOSE_CODES=true` (already in `.env.local`),
  `CPSC_FIXTURE=backend/tests/fixtures/cpsc_recalls.json` (no call to the live CPSC feed).
- Codes: local mail provider is `log`, and the sign-up screen shows "Development build: your code is ……". No email was sent.
  The code itself is not written to `.dev-logs/api.log` (checked).
- Chrome (extension) could not be resized: the window manager keeps it at 1536 px. **Desktop was walked in Chrome;
  390 px was checked with Playwright** (viewport 390×844, `isMobile`, touch) on every page for visitor, member and admin,
  with console, API 4xx/5xx, horizontal scroll, reload and screenshots.
- Camera scanning was not started (the permission prompt would block the browser session).

### Journey table
| # | Journey | 390 px | Desktop | Reload | Console | Network | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | Visitor: text search (`chillmate`, `blender`, no-match) | ok, no h-scroll | ok | kept | clean | all 2xx | PASS |
| 1 | Visitor: barcode search (`012345000024` → fridge) and typed barcode on `/scan` | ok | ok | kept | clean | 2xx | PASS (typed barcode via journey 7–8) |
| 1 | Product page and passport, no account (4 demo states) | ok, bottom tab bar, FAB covers part of trust ring | ok | kept | clean | 2xx | PASS |
| 1 | Passport honesty | — | "No recall found, checks passed" + Version/date; UL "not checked" (not "not certified"); unscored dimensions "No evidence" (no 0) | — | — | — | PASS, except DEF-037 (home hero invents a passport for a real product) |
| 1 | Unknown product / unknown route | "We could not find that product"; NotFound page | same | kept | 404 lines only (expected) | 3× GET 404 | PASS |
| 1 | API unreachable | product page says "could not find that product"; search shows "Cannot reach" **and** "No product matches" | same | — | — | aborted | FAIL, DEF-036 |
| 2 | Sign-up → code → Level 1 | form fits; probe | wrong code → "That code is wrong or has expired." (400); right code → `/rewards`, Level 1, 105 pending | kept | clean | register 201, verify 400/200, login 200 | PASS |
| 2 | Sign-in, session across reload, sign-out | probe with injected session | sign-in as admin and member; reload keeps session; sign-out returns header "Sign in" | kept | clean | logout 204 in API log (the extension's network reader said 503; the server log is authoritative) | PASS |
| 2 | Token expiry | — | bad access + good refresh → exactly **1** `/auth/refresh`, wallet shown; both bad → 1 refresh, "Sign in to continue" | — | — | no storm | PASS |
| 3 | Wallet save / list / remove | Remove invisible on touch (opacity 0), 32 px | save → "In your wallet"; list ok; remove → empty state with a way forward | list kept; **product page forgets saved state** | clean | POST 201, DELETE 204, re-save 409 | FAIL, DEF-030, DEF-038 |
| 3 | Alert on passport change | alert listed | after the safety team confirmed my flag: "MEDIUM · Contoso FastCharge 65W USB-C Adapter: a hazard report was confirmed" + "Passport changed since you saved it" | kept | clean | `GET /alerts` 200 | PASS |
| 4 | Review → re-screen → new passport (async) | form fits | toast "40 TelCoins are pending"; v3 → **v4** (trust 70.14 → 69.76) within ~1 s Worker time; duplicate → toast "You have already reviewed this product." (409) | kept | clean | 201 / 409 | PASS |
| 4 | Helpful vote | — | **no control in the UI**; API: 204, repeat counted once (`helpful_count` 1), own review 409, no token 401 | — | — | — | FAIL, DEF-031 |
| 4 | Hazard flag | form fits | "Report sent to the safety team. You earn 25 TelCoins if it is confirmed." | — | clean | 201 | PASS |
| 4 | Fact report (correction) | form fits | "Correction sent for review…"; accepted by admin → model number now `FC-65-QA`, +20 pending → confirmed | kept | clean | 201 | PASS |
| 5/6 | Coins pending → confirmed, levels, leaderboard | ok | 105 pending → confirmed after the 15 s delay; ledger: level1 100, streak 5, review 10, first review 30, flag 25, fact 20 (all confirmed); Novice, 200 to Inspector; leaderboard ranks "QA Browser" 1st, 190 | kept | clean | 2xx | PASS |
| 6 | Coin store (redemptions) | cards fit | hazard report (50) and watchlist (100) redeemed; page balance 190 → 140 → 40; **header chip stale** | page kept | clean | `/redemptions` 2xx | PASS with DEF-034; the bought report is free to everyone, DEF-035 |
| 7 | Safety team: review queue | cards fit | flag shown with reporter + trust; Confirm hazard (with note) → gone from queue, reporter paid, alert raised, re-screen v5 → v6; correction accepted; member sees "This page is for the safety team." (API 403 `role_not_allowed`) | kept | clean | 2xx | PASS, with DEF-032 (duplicate "Score missing evidence" tasks) |
| 9 | Admin: data sources, run CPSC (fixture) | fits; member sees "This page is for administrators." | "Import recall notices" → job `succeeded` 3 fetched · 3 unchanged; the e2e run's first import: 3 new, **3 `source_records` rows** (`ingestion_jobs` ⋈ `source_records`); `/recalls` lists the notices | kept | `ERR_NAME_NOT_RESOLVED https://example.invalid/heater.jpg` (the CPSC fixture's image URL; renders as an empty frame) | `POST /ingest` 2xx; member 403 | PASS, with DEF-033 (research runs mislabelled) |
| — | Scan page | fits | manual entry, photo and "No barcode?" paths present; camera not started | kept | clean | — | PARTIAL: camera not checked |

### Ownership (404, not 403)
- Member B `DELETE /wallet/items/<member A's item>` → `404 {"detail":"wallet_item_not_found"}`, identical to a random id; A's
  wallet still holds the item. PASS.
- Alerts and coins are only listed for the caller (no by-id read exists to probe). Role checks: member → `GET /review-tasks`
  and `POST /ingest` → 403 `role_not_allowed` (a role, not a row, so 403 is correct).

### Redemption items: what each one does today (record for WO-019; running API = code at `706b0f8`)
| Item | Cost | Kind | Effect observed / in code (`backend/app/modules/rewards/service.py:126-133` at start of run) |
|---|---|---|---|
| `hazard_report_pdf` | 50 | pdf_report | fulfilled at once; `fulfilment.report = /products/<id>/report`; the page is HTML from public reads, ungated (DEF-035) |
| `watchlist_3` | 100 | watchlist_slots | fulfilled at once; `user_entitlements` row `watchlist_slots × 3`, no end date; nothing reads it yet (no watch feature) |
| `api_boost_month` | 200 | rate_limit_boost | entitlement row (code); no business API exists to use it. Not redeemed (not enough coins) |
| `hazard_export_100` | 300 | data_export | stays `processing` (known bug, recorded not failed). Not redeemed |
| `early_access` | 500 | feature_access | entitlement row (code). Not redeemed |
| `subscription_10pct` | 1,000 | invoice_discount | stays `processing` (known bug, recorded not failed). Not redeemed |
Note: during this run another agent was editing `rewards/service.py` in this tree (WO-019). The API ran without `--reload`, so
what is above is the code that was served.

### Observations, not filed
- Hazard label is the weighted total, so a confirmed "electric shock" flag gives Health & Safety 60 yet an overall "Low hazard"
  ((3×5 + 2.5×60 + 1.5×5)/7 = 24.64). This matches `telcron-business-rules` §3. Worth a product decision; `StubScorer` is
  the scorer (named PARTIAL on the page: "Keyword placeholder, not AI").
- Register returns `email_sent: true` with `MAIL_PROVIDER=log` (nothing is sent). For the security verdict.
- Removing a wallet item has no undo (part of DEF-038).
- At 390 px the floating "Ask about this product" button covers part of the trust ring until scrolled.
- Doubled GETs in Chrome's network list are React StrictMode in dev, not a storm.

### `cd e2e && npm run journey`
The first attempt failed on setup, not the product: Playwright's headless shell is not installed. `npx playwright install`
would download it; I did not download anything. So the suite was run with the same spec and config, pointing at the
installed full Chromium (`channel: 'chromium'`) through a config in the scratchpad. On that first run, tests 1–3 failed
because `frontend/node_modules` lacked `lucide-react` until 00:21:13 (installed mid-run; it is in `package.json`), and
tests 5–6 skipped because `SEED_ADMIN_PASSWORD` was not exported. The re-run with the stack settled:

```
Running 8 tests using 1 worker

  ✓  1 [chromium] › journey.spec.ts:10:5 › a visitor searches and reads a passport without an account (3.3s)
  ✓  2 [chromium] › journey.spec.ts:26:5 › members-only pages offer sign-in instead of failing (999ms)
  ✓  3 [chromium] › journey.spec.ts:31:5 › a wrong password is refused with a useful message (1.1s)
  ✓  4 [chromium] › journey.spec.ts:39:5 › a member signs up, saves a product, reviews it and is paid (24.0s)
  ✓  5 [chromium] › journey.spec.ts:88:5 › a hazard report is confirmed by the safety team, pays the reporter and becomes evidence (7.8s)
  ✓  6 [chromium] › journey.spec.ts:131:5 › an admin imports recall notices and visitors can search them (6.3s)
  ✓  7 [chromium] › journey.spec.ts:158:5 › a barcode leads straight to the product passport (3.3s)
  ✓  8 [chromium] › journey.spec.ts:180:5 › a product no database knows is identified by a member and screened (10.0s)

  8 passed (57.8s)
```
No file under `e2e/` was changed. Suggested for the owner of the machine: `cd e2e && npx playwright install chromium`.

### Not tested
- Camera scanning (permission prompt; no camera in the session). Photo identification: only the presence of the path.
- Real email delivery (out of scope; `log` provider). Google sign-in (not built). Level 2 (not built).
- The live dev site and AWS (out of scope this run).
- `data_export` / `invoice_discount` / `api_boost` / `early_access` redemptions (the member had 190 coins).

### Data created on the local database
Members `qa-browser-1795287170@example.com` ("QA Browser") and `qa-browser-b-…@example.com` ("QA Browser B"), one review, one
confirmed flag and one accepted correction on `contoso-fastcharge-65w` (model number is now `FC-65-QA`), two redemptions, a
helpful vote on the demo review, one CPSC job. Plus the e2e suite's own members (two runs).
