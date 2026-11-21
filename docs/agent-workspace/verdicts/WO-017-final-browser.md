# WO-017 final browser gate (PLAN §5 check 2)

## Browser QA: WO-017 / DEF-030…038, 011, 012, 014, 043, 044 · WO-019 · WO-055 · WO-056
Environment: local · branch `week-02` @ `838beea` · 2026-11-22 · Personas: visitor, member L1 (four), moderator (two), admin
Agent: browser-qa-engineer · New DEFs: **DEF-100, DEF-101** (both S4, frontend-engineer)

### Setup
- Settings exported in the shell only (same `env.sh` as run 2 in the agent scratchpad: `SEED_ADMIN_PASSWORD`,
  `COIN_CONFIRM_DELAY_SECONDS=15`, `DEV_EXPOSE_CODES=true`, `CPSC_FIXTURE`). `.env` not touched.
- `make app-db` (evidence for WO-022 / WO-019):
  ```
  docker compose run --rm migrate up
  Applying: 20261122130000_phase2_schema.sql
  Applied: 20261122130000_phase2_schema.sql in 20.073517ms
  Applying: 20261122130100_phase2_rules.sql
  Applied: 20261122130100_phase2_rules.sql in 8.683951ms
  Applying: 20261122130200_phase3_schema.sql
  Applied: 20261122130200_phase3_schema.sql in 10.754221ms
  Applying: 20261122130300_phase3_rules.sql
  Applied: 20261122130300_phase3_rules.sql in 7.556198ms
  Applying: 20261122130400_phase2_3_reference.sql
  Applied: 20261122130400_phase2_3_reference.sql in 15.960381ms
  Applying: 20261122140000_redemptions_phase_one.sql
  Applied: 20261122140000_redemptions_phase_one.sql in 21.116273ms
  seeding db/seeds/001_core_reference.sql
  NOTICE:  demo data already present — skipping
  admin: admin@telcron.example.com
  coin delay: 15s
  ```
  dbmate prints "Applied" for the phase 2–3 files and hides the `RAISE NOTICE … skipped`. Run times of 8–20 ms and
  the data show they skipped. Existing phase-2 data survived: `hazard_assessments` 13 rows, created
  2026-11-21 18:50–18:59 UTC (before this run), and run 2's members are still there. `schema_migrations` holds all six
  versions. Redemption migration applied: `redemption_items` active = `hazard_report_pdf`, `watchlist_3` only, and
  redemptions `processing` = 0.
- `make dev`: `/health` → `{"status":"ok","version":"dev"}`. The Worker was running throughout (`.dev-logs/worker.pid`
  child alive; coins confirmed, passports re-issued).
- Tools: Playwright with the installed full Chromium (`channel: 'chromium'`), because the headless shell is still
  not installed; **nothing downloaded**. Every check ran at 390×844 (`isMobile`, touch) and at 1280×800, with console,
  API ≥ 400, external requests, horizontal scroll and reload. The Chrome extension was used for a desktop spot check
  of the passport page's network list and console (all 2xx, console clean).
- **Concurrent edit:** during the run another agent changed `backend/app/modules/catalogue/service.py` (+55/−10,
  mtime 01:09 IST) and `WO-021.md` in this tree. The API ran without `--reload` and was last started at 01:01, so it
  served what was on disk then. This verdict is for that code, not for a later version of `catalogue/service.py`.

### Criteria
| Item | Verdict | Evidence |
|---|---|---|
| DEF-030 saved state after reload | PASS | phone + desktop: "Save to wallet" → "In your wallet" → reload → "In your wallet" |
| DEF-031 helpful vote | PASS | Members see "Helpful" (44 px) on other people's reviews; no button on their own review ("QA Final C" card: 0). Click → `POST /reviews/<id>/helpful 204`. After clearing `telcron.helpful:*` from localStorage and reloading, it still shows "You found this helpful" (server `voted`). Both widths |
| DEF-033 data sources | PASS | Separate "Recall imports" and "Product research runs" sections. Research rows say "Product research · open the product · automatic (new or due product) / a member asked"; errors as sentences ("Web search: no search provider configured."). Note: the row links to the product but does not name it |
| DEF-034 header coins after a redemption | PASS | phone: chip 140 → 90 at once (`POST /redemptions 201` → `/auth/me` → `/coins`), 90 after reload; desktop: 105 → 5, 5 after reload |
| DEF-036 API stopped | PASS (with DEF-100) | API process really stopped. Product: "This product could not be loaded · Could not reach Telcron. Check your connection and try again. · Try again". Search and recalls: the same alert, no empty state, no endless spinner. Restarted, healthy. **DEF-100:** a signed-in member on `/wallet` and `/rewards` is shown "Sign in to continue", and the header shows "Sign in". The session is kept and comes back after the API returns |
| DEF-037 home passport is real | PASS | Desktop hero = `/products/contoso-fastcharge-65w`: "v6 · Certificate issue · 70 · No recall notice names it · Low hazard · Regulatory Flags 5 · Health & Safety 60 · Customer Issues 5". API: version 6, `certification_issue`, trust 69.76, Low, 0 matches, same three dimensions. It is hidden below `lg` (phone) by design |
| DEF-038 wallet Remove | PASS | 44×44, opacity 1, visible without hover, at 390 px and desktop |
| DEF-014 paged list depth on reload | PASS | `/rewards` history: 8 → Load more → 10 → reload 10 → back 10 (phone + desktop). Observation: whether a typed address opens at the top or at the stored depth depended on the order of earlier visits (key `telcron.paged:default:/coins/history`). Not filed |
| WO-055 admin shell | PASS | admin nav: Overview/Data sources/Review queue. Moderator: Overview/Review queue; `/admin/data-sources` → "That page does not exist.". Member: not found on all three. Visitor: "Sign in to continue". `/data-sources` → `/admin/data-sources`, `/review-queue` → `/admin/review-queue`. Each kept after reload, no h-scroll, console clean, both widths |
| WO-019 store | PASS | `/rewards` store lists only "Full hazard report (PDF)" (50) and "Watchlist alerts for 3 products" (100). Redemptions `fulfilled`: report `{"report": "/products/<id>/report"}`; watchlist: `user_entitlements` `watchlist_slots × 3`. Off-sale `api_boost_month` → `404 item_not_found`. History "Spent in the store … Confirmed −50 / −100" |
| DEF-011 own flag / own hold | PASS (with DEF-101) | Moderator 1 tried all 3 buttons on their own flag and all 3 on their own hold: each `POST …/resolve 403`, with "You cannot decide on your own item. Leave it for a colleague.". Both still in the queue after reload; frozen coins unchanged. **DEF-101:** the buttons are offered anyway, and they are 38 px tall on a phone |
| DEF-012 dismiss leaves nothing pending | PASS | Moderator 2 dismissed member D's flag: flag `rejected`; member D's rewards show the note "Closed by the safety team without a finding." They dismissed moderator 1's hold: hold `released`, moderator 1's coins confirmed 145 / frozen 0. Tasks `dismissed` |
| DEF-043 same screen for an existing address | PASS | Register `201` for both. Existing and new addresses get the same "Check your email … If it says you already have an account, sign in instead." screen. The only difference is the local-only dev-code notice (DEF-048, local/test only) |
| DEF-044 rate limit | PASS | 20 wrong codes → `400` "That code is wrong or has expired."; the 21st → `429` "Too many tries from here. Try again in 60 minutes." |
| WO-056 flags | PASS | `GET /api/v1/flags` → `200 {"flags":{}}`, `cache-control: public, max-age=60` |

### Asynchronous loop
Member C flagged the Northwind fridge. Moderator 2 confirmed it at 19:32:53 UTC. Passport v5 → **v6** (Worker).
`alerts` for member D (holds it in their wallet): "MEDIUM · Northwind ChillMate … a hazard report was confirmed"
created 19:32:53.04. Member C's coins: 140 confirmed, 0 pending after the 15 s delay (flag +25 included). After
reload, the queue no longer shows the task.

### Performance (6 products, local; Resource Timing in Chromium, two requests per load = React StrictMode)
- Cached passport `GET /products/<slug>/passport` (Redis `telcron:passport:*` present): **11–32 ms**, first miss
  55 ms (acme). curl: 6–25 ms. Target < 300 ms: PASS at demo volume.
- Search `GET /products?q=`: 8–26 ms (text, barcode, no match); curl 7–8 ms. These are demo-size figures. The
  known trigram scan risk at volume (`telcron-performance`) is not measured here.

### Console · Network
- New errors: none apart from the expected ones: 403 per click on own items (DEF-101), 429 at the rate limit,
  `ERR_CONNECTION_REFUSED` with the API stopped. `ERR_NAME_NOT_RESOLVED` on home/recalls comes from the CPSC
  fixture's `example.invalid` image (known since run 2).
- External requests: Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`, `frontend/index.html:9-11`),
  present before this week. Noted for the privacy review, not filed.

### Phone · desktop
No horizontal scroll on any page walked, at either width. Tap targets: Remove and Helpful are 44 px; the queue
buttons are 38 px (DEF-101).

### `cd e2e && npm run journey`
`npm run journey` cannot launch: the headless shell is not installed (same as run 2), and I did not download it. Run
with the same spec through a scratchpad config pointing at the installed Chromium. The first run had 2 failures.
Both were stale assertions after WO-055 (a member on `/review-queue` expected "This page is for the safety team.";
a visitor on `/data-sources` expected "This page is for administrators."). A later run had 1 flaky failure: test 1
asserted the Acme link before the search page loaded, and the real home passport card (DEF-037) also links to
Acme. I updated `e2e/journey.spec.ts` (my lane): the not-found page and the sign-in prompt with the
`/admin/...` URL, and a wait for `/search?q=blender`. `npx tsc --noEmit` ok. Final:
```
Running 8 tests using 1 worker
  ✓  1 [chromium] › journey.spec.ts:10:5 › a visitor searches and reads a passport without an account (3.2s)
  ✓  2 [chromium] › journey.spec.ts:28:5 › members-only pages offer sign-in instead of failing (959ms)
  ✓  3 [chromium] › journey.spec.ts:33:5 › a wrong password is refused with a useful message (1.2s)
  ✓  4 [chromium] › journey.spec.ts:41:5 › a member signs up, saves a product, reviews it and is paid (22.0s)
  ✓  5 [chromium] › journey.spec.ts:90:5 › a hazard report is confirmed by the safety team, pays the reporter and becomes evidence (9.9s)
  ✓  6 [chromium] › journey.spec.ts:134:5 › an admin imports recall notices and visitors can search them (6.0s)
  ✓  7 [chromium] › journey.spec.ts:162:5 › a barcode leads straight to the product passport (2.2s)
  ✓  8 [chromium] › journey.spec.ts:184:5 › a product no database knows is identified by a member and screened (8.2s)
  8 passed (54.5s)
```
Without this change the CI journey gate on `main` would fail on tests 5 and 6.

### Not tested
Camera scanning; real email (log provider); the live site and AWS; the hazard report page's gating (DEF-035, not in
this list); search performance at volume.

### Data created on the local database
Members `qa-final-memberc-…`, `qa-final-memberd-…`, `qa-final-rl-…` (rate-limited, unverified), moderators
`qa-final-mod1-…` and `qa-final-mod2-…` (role set by SQL). Created through the API: reviews (A on acme, C on
northwind, mod1 on the lamp) and flags (C confirmed, D rejected; mod1's lamp flag is still **open** for a colleague).
One fraud hold, inserted by SQL and released. Two redemptions, helpful votes, the e2e suite's own members and three
CPSC jobs. Screenshots:
`/tmp/claude-1000/-home-silverblade-Startups-CodeGang-Projects-Telcron-Codebase/f710e93c-b080-41fd-939f-13a2583168e0/scratchpad/final/shots/`.
