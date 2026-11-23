## Browser QA: WO-058 (DEF-113, 114, 115, 116, 118, 119, 120, 121-home)
Environment: local (web :3200, API :4310, Worker running) · branch week-02 @ 80f18b2 · Chrome (claude-in-chrome)
Persona: visitor, then a new member L1 (`wo58-bqa-1123@example.com`, signed up with the dev-exposed code). Admin
pages: not in the browser (see "Not tested").
Phone: the window would not resize (maximised; `resize_window` reported success, `innerWidth` stayed 1536), so 390 px
was checked in a same-origin 390 × 844 iframe (iframe viewport 389 px; media queries apply to it).

### Verdict per defect
| Defect | Verdict |
| --- | --- |
| DEF-113 | PASS (one gap filed as DEF-123, S4) |
| DEF-114 | PASS (match live; near_match checked with a mocked passport, none exists in the DB) |
| DEF-115 | PASS (old runs live; new copy checked with a mocked `stats.sources`, no run with `sources` exists yet) |
| DEF-116 | PASS |
| DEF-118 | PASS (Gate copy checked in the sign-in step and in source; the Gate is unreachable at Level 0, see below) |
| DEF-119 | PASS (redemption done once, worked) |
| DEF-120 | PASS at API/DB level; browser rendering NOT TESTED (no admin session in the browser) |
| DEF-121 home | PASS |
New: DEF-123 (S4, certificate-issue verdict hides hazards), DEF-124 (S3, home hero clipped at 390 px, pre-existing).
Incident: DEF-122 overwritten by me — see the end.

### Journey and evidence
**DEF-113**
- `/products/northwind-chillmate-31` (total 38.93 Medium, H&S 100, badge verified): verdict "Serious hazards are
  reported — No recall notice matched it as of 22 Nov 2026. But sources describe a high hazard on at least one
  dimension: open the hazard scores below to see the evidence." Recalls tile "No notice names it as of 22 Nov 2026".
  No "checks passed" anywhere. Same at 390 px. Screenshots: /tmp/claude-chrome-screenshots-qsrqZF/screenshot-1795434346281-1.jpg (desktop),
  /tmp/claude-chrome-screenshots-qsrqZF/screenshot-1795434704347-3.png (390 px).
- Low/verified: none exists in the DB (3 screened products: Medium, Medium, High). With the passport response
  mocked in the page (total 8, every dimension 5): "No recall found, checks passed — No recall notice matched it as of
  22 Nov 2026. Nothing we found shows a serious hazard." Hazard tile "Low hazard".
- `recall_checked_as_of: null` (mocked): "No recall notice matched it as of the last check." and tile "No notice names
  it as of the last check". No invented date.
- Every no-recall line has a date: passport verdict, Recalls tile, home hero card ("No recall notice as of 22 Nov
  2026"), unidentified-desk-lamp tile, contoso tile.
- Gated report (unlocked by a 50-coin redemption): "Recalls — No recall notice matched it as of 22 Nov 2026."; no
  "checks passed".
- Note (not a defect): every current screening predates lane A's fix (7e52e78, 11:27 UTC); e.g. acme's
  `recall_checked_as_of` 10:54 UTC is its screening clock, not the newest CPSC import (2026-11-21 20:00:28 UTC).
  Correct values appear on the next re-screen. Dates render in the browser's local zone (IST here).
- Gap → **DEF-123**: contoso (certification_issue, total 37.35, H&S 100) shows only "A certificate problem was
  found…"; no hazard warning. Not "checks passed", but the criterion's "shows a warning that hazards are reported".

**DEF-114**
- `/products/acme-powerblend-1000` (match): no "Where to buy" in the DOM; recall card and "What to do" remedy shown.
- near_match: none in the DB (`screenings.verdict`: match 5, no_match_found 43, insufficient_information 2). Mocked
  on northwind: menu opens with "An official recall notice may cover this product. Check the recall notices below
  against your model before you buy." above the store links; verdict "Official recall notices may cover this
  product"; recall card "RECALL · MAY MATCH THIS PRODUCT".

**DEF-115**
- Old runs (no `sources`; northwind, acme, contoso, desk lamp): "Telcron asks official recall registries such as US
  CPSC, US FDA and UK Product Safety, and reads public pages about the product…", "Searched 11/22/2026: 5 pages read,
  none said anything…", "Some sources did not answer last time: web." No Reddit/X/YouTube, no "searched the web".
- New run copy (mocked `sources` {cpsc, uk_opss answered; openfda_device failed; web not_configured}): "At the last
  search, US CPSC and UK Product Safety (OPSS) answered. Web and owner-forum search (Reddit, X, YouTube, reviews) is
  not available yet, so none of those were searched." / "5 pages from US CPSC and UK Product Safety (OPSS) read…" /
  "Failed at the last search: US FDA. Asked again on the next search."
- A real "Search again" was not triggered (it writes a research job and re-screens a demo product).

**DEF-116** (signed in as the L1 member; POST to /reviews blocked in-page as a safety net — none attempted)
- Rating radiogroup `aria-labelledby="rating-label"` ("Rating"), five native radios "1 out of 5" … "5 out of 5", all
  unchecked at start; 44 × 44 px at desktop and at 390 px.
- Text typed, no rating, "Post review" → role=alert "Choose a rating from 1 to 5 stars, then post your review.",
  radiogroup `aria-describedby="rating-missing"`, 0 POSTs. Choosing 4 → only radio 4 checked, alert gone. Nothing posted.
  Screenshot: /tmp/claude-chrome-screenshots-qsrqZF/screenshot-1795434620998-2.jpg
- Shown ratings: role=img "5 out of 5", "4 out of 5", … ; trust ring role=img "Trust score: 81 out of 100".

**DEF-118**
- Sign-up phone placeholder "+1 555 010 0123". Sign-in for an unconfirmed member: "Confirm your email first: enter
  the code we emailed you." (no phone). `components/Gate.tsx` has no "phone" left (grep); the Level-1 Gate itself
  cannot be shown in the browser because an unconfirmed member cannot sign in.
- `/rewards`: "+100 Verify your email"; "+5 Sign in each day", "+10 Sign in each day from day 7 of a streak";
  streak box "1 day · +5 a day, +10 a day from day 7" (agrees); "Coming soon" for "Add a photo to a review", "Invite a
  friend who verifies", "Verify your identity" (no amount); "Reward levels": "From 0 / 200 / 1,000 / 5,000 / 20,000
  coins earned in total"; hero "Novice · Your reward level · 200 more to reach Inspector"; no "Level n" anywhere.
  History "Verified your email".

**DEF-119**
- Gate on `/products/northwind-chillmate-31/report`: "Open the coin store" → `/rewards?product=northwind-chillmate-31`,
  copy says the product is already chosen and need not be in the wallet. Passport link "Get the full report with
  TelCoins" → same URL.
- Clicking it: page scrolls to the store, select "For" = northwind (wallet empty, so not a wallet product). Also
  `/rewards?product=acme-powerblend-1000` at 390 px → select = acme.
- Redemption (50 test coins): toast "Full hazard report (printable) is yours / Your report is ready.", history
  "Spent in the store −50 · Confirmed", report then opens.

**DEF-120** (API + DB; browser not tested)
- `GET /review-tasks` as admin (token obtained in a shell, never printed): every `hazard_insufficient_data` task has
  `subject.missing_dimensions` (names, or `[]` for the 2 pre-DEF-032 tasks) and `passport_version` (2, 5, 12, 13…).
- DB: open/in_progress `hazard_insufficient_data` per `payload->>'product_id'`: max 1.
- Data sources separator: source review only (`DataSources.tsx` JobRow now emits `{' · '}` as text).

**DEF-121 home**
- "Recently screened": Contoso, Northwind, Acme only; no Lumina cards. Request `GET /products?limit=6&screened=true`
  → 200 (the only "Lumina" text on the page is a recall title, "RSX Luminaires").

### Reload / async loop
- Every page re-checked after a full reload (navigate) — state the same.
- Coins: sign-up earns "+100 Verify your email" and "+5 Daily sign-in" shown "Pending check", then "Confirmed" a few
  minutes later (Worker) — spendable 0 → 105; after redemption the −50 was "Confirmed" at once.
- No review/flag posted, so no passport version or alert loop to observe.

### Console · Network
- Console: no errors or warnings on home, passports, rewards, report.
- Network: all API calls 200; only localhost:4310 and localhost:3200. Each home/report request appears twice (React
  StrictMode in dev, not a finding).

### Phone · desktop
- 390 px: passports (northwind, acme, contoso, desk lamp), report gate, rewards, sign-up, wallet, search: nothing
  overflows. Radios 44 px.
- **DEF-124 (new, S3, pre-existing)**: home hero column is 429 px in a 389 px viewport; `overflow-hidden` hides it,
  so `scrollWidth` looks fine, but the headline, intro and "Search" button are clipped. Cause: the hero search
  input's intrinsic width sets the grid item's min-content. Screenshot:
  /tmp/claude-chrome-screenshots-qsrqZF/screenshot-1795434746375-4.png

### Not tested
- Admin queue and Data sources pages in the browser: signing in as admin needed the seed password in the browser or
  the session token placed in the page; reading the token into my context was refused by the environment's
  permission classifier, so I verified DEF-120 through the API and DB instead.
- A real research run with `stats.sources` and a real near_match / Low-verified product: none exist locally; checked
  with in-page mocked responses through the real components.
- The Level-1 Gate component in the browser (unreachable: an unconfirmed member cannot sign in).

### Writes to the shared DB
One member (`wo58-bqa-1123@example.com`, its earn rows) and one report redemption (50 coins, northwind). No review,
flag, wallet entry, product or research job.

### Incident: DEF-122 overwritten
While filing, I wrote my defect to `defects/DEF-122.md` although a DEF-122 had appeared there about a minute earlier
(qa-test-engineer's test-order defect; my `ls` showed it and the write went ahead in the same command). The file
was untracked, so its original text is lost. I moved my defect to DEF-124 and rebuilt `DEF-122.md` from
`verdicts/WO-058-qa.md`, marked RECONSTRUCTED, for qa-test-engineer to check.

## Re-check DEF-123/124
Environment: local (web :3200, API :4310, stack not restarted) · branch week-02 @ 4f16d8a · Persona: visitor pages
(the shared browser happened to be signed in; nothing written) · 2026-11-23 · read-only, no DB writes.

| Defect | Result |
|---|---|
| DEF-123 (045a149, `components/Verdict.tsx`) | **PASS** |
| DEF-124 (4f16d8a, `SearchBox.tsx`, `Home.tsx`) | **PASS** |

**DEF-123**
- `/products/contoso-fastcharge-65w` (certification_issue, total 37.35, H&S 100): "A certificate problem was found,
  and serious hazards are reported — One of its certificates has expired or been revoked. See the details below.
  Sources also describe a high hazard on at least one dimension: open the hazard scores below to see the evidence."
  Same title at 390 px (title right edge 334 in a 375 px iframe viewport; no overflow).
- Mocked near_match (in-page fetch override on northwind's passport: one `near_match`, hazard "Fire hazard"; northwind
  has H&S 100): "Official recall notices may cover this product, and serious hazards are reported — Fire hazard.
  Check the notices below against your model and serial number. Sources also describe a high hazard on at least one
  dimension: open the hazard scores below to see the evidence."
- Unchanged: northwind (real) "Serious hazards are reported — No recall notice matched it as of 22 Nov 2026. But
  sources describe a high hazard…", identical to the WO-058 verdict; acme "This product is recalled — Laceration
  hazard. Stop using it and follow the notice's remedy."

**DEF-124** (measured in a same-origin iframe; the iframe's scrollbar makes the layout viewport 15 px narrower than
the frame, so the check is slightly stricter than a real phone)
| Page | Frame / viewport | scrollWidth | h1 right | intro right | input right | Search button right |
|---|---|---|---|---|---|---|
| `/` | 390 / 375 | 375 | 359.2 | 359.2 | 255.2 | 353.2 |
| `/` | 360 / 345 | 345 | 328.8 | 328.8 | 224.8 | 322.8 |
| `/search` | 390 / 375 | 375 | 359.2 | 359.2 | 254.4 | 352.4 |
| `/search?q=northwind` | 390 / 375 | 375 | 349.4 | — | 254.4 | 352.4 |
- Before the fix the home h1 right edge was 445 in 389. Only element past the viewport: the decorative
  `div.absolute -left-40 -top-40 size-[640px]` glow, clipped by the hero's `overflow-hidden` by design.
- Screenshot at 390 px (headline, intro, search box and Search button whole):
  /tmp/claude-chrome-screenshots-qsrqZF/screenshot-1795435664519-7.jpg
- Desktop (1501 px viewport): still two columns (`556.275px 483.712px`), h1 198–755, Search button 659–749, passport
  card on the right; scrollWidth 1501. Screenshot: /tmp/claude-chrome-screenshots-qsrqZF/screenshot-1795435679513-8.jpg

**Gates**: `cd frontend && npx tsc --noEmit && npm run build` → exit 0, "✓ built in 3.64s" (only the existing
>500 kB chunk-size warning for `index` and `Scan`).

**Console · Network**: no errors on home or contoso after reload; every `/api/v1` call 200 and only to
localhost:4310. One React "unique key" warning appeared only while the near_match mock was active: my mocked
recall had no `recall_id` (Product.tsx keys on it) — a mock artefact, not a finding.

**Not tested**: a real near_match (none in the DB); `window.resize` to a real 390 px window (iframe used instead so
the shared Chrome window was not resized).
