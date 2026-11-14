# Prompt — Telcron Database Design (Logical + Physical ERD)

> Reusable design brief. Run it whenever the ERD is redesigned or extended.
> Inputs live in `../Resources/`, `../Technical_Documentation/` and `../Notes/` (outside this repo).

---

## Role

You are a principal data architect designing the system-of-record database for **Telcron**, a
consumer product-safety platform. You design schemas that survive years of changing
requirements: correct first, explicit about invariants, cheap to evolve, and pleasant for
application developers to query. You justify every non-obvious choice.

## Business context (read before designing)

Telcron is "**ID.me for products**": verify a product's identity and safety once, issue a reusable
credential (the **Product Passport**), and let every surface (web app, future mobile app, Chrome
extension, partner API) trust it.

Core loop:
1. **Capture** — user submits a photo/video, barcode, or brand + model text.
2. **Identify** — AI resolves it to ONE canonical product record; marketplace IDs (UPC/EAN/GTIN,
   ASIN, eBay item, Best Buy SKU, model number) are *aliases* of that record. Identification runs
   once per product ("identify once, cache forever"). Below a confidence threshold the user is
   prompted for manufacturer + model (Tier 0 → fallback, a designed outcome).
3. **Verify** — screen against official recall sources (CPSC, openFDA, later NHTSA/EU/CA…) and
   certification sources (FCC, Energy Star; UL/ETL "Not checked" until access exists). Every verdict
   cites its source record. Verdicts: `match | near_match | no_match_found | insufficient_information`.
   Cert statuses: `valid | expired | revoked | not_found | not_checked` ("not checked" is never
   "not certified").
4. **Passport** — versioned record: tier (0 Unidentified, 1 Identified, 2 Verified), status badge
   (Verified, Recalled, Certification issue, Needs info), trust score 0–100, evidence citations,
   verified-at timestamp, QR / public link. A recall match always forces the Recalled badge.
5. **Re-screen** — products held in user wallets are re-screened at least daily against newly
   synced recalls; status changes create risk events and notifications.

Wider Phase-1 scope (Feature List V2, TC-P1-001…029) built on that core:
- Accounts: in-house auth (email + password, Google OAuth; Facebook later), email + phone
  verification → Level 1; optional ID document + selfie → Level 2 (only the *result* is stored,
  never ID images); Level 3 business is out of scope but must not be blocked. Trust score 0–100
  driven by auditable events. Sessions: 90 min max, 20 min idle. Every login attempt audited.
- Media: user uploads (image/video) → EXIF strip, ≤1024px normalise, perceptual hash dedupe,
  moderation, CLIP/Nova embeddings, AI labels/annotations with confidence and bounding boxes.
- Ingestion: API-only (no scraping) from Amazon, eBay, Best Buy, Bonanza, CPSC, FDA, Reddit,
  TikTok…; raw payload kept for reprocessing; categories onboarded by configuration only.
- Traceability: product → manufacturer/model resolved from commerce sources, evidence kept forever.
- Hazard scoring: 7 configurable weighted dimensions (Regulatory 3.0, Health & Safety 2.5,
  Customer Issues 1.5, Fragility 1.5, Environmental 1.0, Regional 1.0, Animal 0.5); every
  dimension needs a citation (text chunk or image bbox) else "insufficient data"; alert threshold
  configurable (80); must support future scoring contexts (sustainability, circularity).
- Digital Wallet: save products (add via dashboard/media grid, manual entry, barcode), notes,
  custom labels, soft delete, history retained (never silently overwritten), short-video
  verification for manual/barcode adds, QR label generation (iotsecurityprivacy.org), capped list.
- Rewards: TelCoins append-only ledger (pending → confirmed / frozen / clawed back), earn rules
  (100 L1, 500 L2, 10 review, 15 photo, 25 confirmed hazard flag, 5/10 streak, 50 referral, 20 fact
  verification, 30 first-reviewer), 500/day cap, rapid-fire fraud holds, redemption catalogue
  (50 hazard PDF, 200 API boost, 500 early access, 100 watchlist alerts, 300 export, 1000 discount),
  spend only confirmed coins; user level (Novice→Master) from LIFETIME earned with earn bonus %.
- Community: posts (with media, location, tagged product), reviews (title, body, 1–5 rating,
  photo, helpful votes, edit/delete own), hazard flags (pending/confirmed/rejected, matched against
  recalls), comments, reactions, community feed filtered by location/product/category.
- Commerce feed: For You / Explore tabs, filters Country × Source × Category × Topic (Market
  Acceptance, Sustainability, Cyber, Recalls, Circularity, Wireless), AI label + confidence per item.
- Price tracking: price snapshots per source/seller/currency, target-price alerts.
- Risk Event Timeline: risk instances (recall / hazard / price / certification) grouped by day,
  with evidence and media, user confirms or dismisses; notifications.
- Audit: every identification, verification, passport change, alert, coin movement and admin
  action is append-only and permanent.

Out of scope (do not model, but do not paint into a corner): business/org login & dashboards,
billing/payments, cart/checkout, internal messaging, personal data-source integrations, scraping.

## Fixed decisions

- **PostgreSQL 18** (native `uuidv7()`), extensions: `pgvector`, `pg_trgm`, `postgis`, `citext`.
- Auth is **built in-house** (no Cognito). Google OAuth + email/password. Google users must still
  verify a phone number to reach Level 1.
- Design the **full logical model**, mark a **core subset** to be created first (enough for auth,
  product page, passport, recalls, certifications, wallet, reviews). Remaining domains land later as
  additive migrations.
- Deliverable diagram format: **draw.io**, matching the style of the existing Telcron diagrams.

## Design principles (non-negotiable)

1. **Single source of truth.** No value stored in two places unless it is an explicitly labelled,
   rebuildable denormalisation (e.g. current-passport pointer, cached balance).
2. **Invariants in the database**, not only in code: PK/FK, `UNIQUE`, `CHECK`, `NOT NULL`, partial
   unique indexes, exclusion constraints where useful.
3. **Append-only where history matters** (ledger, audit, screenings, certification checks,
   passports versions, trust events, price snapshots). Corrections are new rows, never updates.
4. **Reference data vs. user data vs. derived data** clearly separated (recalls/certs are external
   reference; wallets/posts are user-owned; passports/scores are derived and reproducible).
5. **Normalise to 3NF**; use `JSONB` only for genuinely schemaless payloads (raw source records,
   model outputs, per-source extras), never for data we filter/join on.
6. **Configuration as data** (categories, hazard dimensions & weights, earn rules, redemption items,
   topics, data sources) so behaviour changes without deploys.
7. **Provenance everywhere**: who/what created a row (user, system job, model + version, source).
8. **Privacy by design**: minimal PII, isolated in the identity domain; no ID document images; hashed
   tokens/OTPs/passwords; public passport exposes product data only; soft-delete + anonymise path
   for account deletion (GDPR/CCPA-style).
9. **Evolvability**: polymorphic links via explicit typed join tables or nullable FK + CHECK
   (exactly-one-of), not untyped `(type, id)` pairs, unless documented.
10. **Query-pattern aware**: name the main read paths per domain and index for them.

## Conventions

- `snake_case`, plural table names, singular column names; FK = `<entity>_id`.
- PK `id uuid DEFAULT uuidv7()`; config/lookup tables may use a natural text `code` PK.
- Every table: `created_at timestamptz NOT NULL DEFAULT now()`; mutable tables add `updated_at`;
  soft-deletable tables add `deleted_at`.
- Status / type columns: Postgres enums for stable sets, lookup tables for business-configurable sets.
- Money: `numeric(12,2)` + ISO-4217 `currency char(3)`. Coins: `bigint`. Scores: `numeric(5,2)`.
- Time ranges and geography: `tstzrange`, PostGIS `geography(Point,4326)`, ISO-3166 country codes.
- Embeddings: `vector(n)` in dedicated tables keyed by model, so models can change.

## Deliverables

1. `docs/database/telcron-erd.drawio` — multi-page draw.io file:
   - Page 1 **Overview**: domains as coloured groups and the key relationships between them.
   - One page per domain cluster with full columns (PK/FK/UK markers, types), crow's-foot edges.
   - Core (create-first) tables visually marked.
2. `docs/database/schema-design.md` — design rationale: domains, table catalogue (purpose,
   key columns, constraints, indexes, core/later), invariants, key read paths, decisions & open
   questions, and how it maps back to Feature IDs (TC-P1-xxx).
3. Export PNG/SVG previews for review.

## Self-review checklist (run before presenting)

- [ ] Every Feature V2 item maps to tables, or is explicitly out of scope.
- [ ] Every Month-1 passport invariant is enforceable (one canonical product per alias, recall
      match → Recalled badge, uncited verdict impossible, "not_checked" ≠ "not_found").
- [ ] Ledger: no double-spend possible, balance derivable from rows, clawback traceable, daily cap
      computable with one indexed query.
- [ ] No orphan-able rows; ON DELETE behaviour chosen deliberately per FK.
- [ ] No PII outside the identity domain except references by `user_id`.
- [ ] Each domain lists its top 3 read paths and the indexes serving them.
- [ ] Nothing duplicated without a documented reason.
- [ ] Diagram is readable: no crossing spaghetti, consistent colours, legend present.
