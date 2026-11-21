# Telcron — Database Design

| | |
|---|---|
| **Status** | v0.2 — reviewed, tested, core created locally · 2026-11-14 |
| **Engine** | PostgreSQL 18 · extensions `citext`, `pg_trgm`, `btree_gist`, `postgis`, `vector` (pgvector 0.8) |
| **Scope** | Full logical model for Feature List V2 (TC-P1-001…029) + Month-1 Passport engine (FR-01…17) |
| **Size** | 90 tables in 14 domains · 61 enums · 173 FK columns + 11 composite FKs |
| **Phases** | **1 core: 38 tables (created now)** · 2 AI engine: 14 · 3 engagement: 38 |
| **Diagram** | [`telcron-erd.drawio`](telcron-erd.drawio) — overview + 9 domain pages; PNG previews in `preview/` |
| **Source of truth** | [`schema_spec.py`](schema_spec.py) → `make db-gen` regenerates SQL, diagram and §12 |
| **Tests** | `db/tests` — 66 invariant/behaviour tests + 13 read-path performance tests, all passing (§10) |
| **Design brief** | [`../prompts/erd-design-prompt.md`](../prompts/erd-design-prompt.md) |

> Requirements are still moving (the overall architecture is being redesigned). The model is
> **additive-friendly**: phases 2–3 only add tables/FKs pointing into the core, so the core never
> has to change shape. Items needing a business decision are listed in §11.

---

## 1. What the database must do

Telcron is "ID.me for products": a product is captured, **identified once** into a canonical
record, **verified** against official recall and certification sources with **cited evidence**,
issued a versioned **Product Passport**, kept in users' **wallets**, and **re-screened** as new
recalls publish. Around that core: TelCoins rewards, community content, a commerce feed, price
tracking and a risk-event timeline.

The data has four natures, which drive most decisions:

| Nature | Domains | Rule |
|---|---|---|
| **Reference** (external truth) | Sources, Recalls, Certifications | Synced, never user-edited; raw payload versioned |
| **Registry** (our canonical truth) | Catalogue, Media | One record per real thing; merged, never deleted |
| **Derived** (reproducible) | Screening, Hazard, Passport, Risk events | Append-only runs; recomputable from reference + registry |
| **User-owned** | Identity, Wallet, Community, Rewards, Feed history, Price alerts | Personal data; anonymise path on account deletion |

## 2. Conventions

- `snake_case`; plural tables; FK columns `<entity>_id`; stable code-owned sets are Postgres enums,
  business-configurable sets are lookup tables (`data_sources`, `hazard_dimensions`, `coin_earn_rules`…).
- PK `id uuid DEFAULT uuidv7()` — time-ordered (index-friendly), safe to expose. Lookups use a text `code` PK.
- `created_at timestamptz NOT NULL DEFAULT now()`; `updated_at` maintained by trigger; `deleted_at` soft delete.
- Money `numeric(12,2)` + `char(3)` ISO-4217; coins `bigint`; scores `numeric(5,2)` 0–100; confidences
  `numeric(4,3)` 0–1; countries ISO-3166-1 `char(2)`, regions ISO-3166-2 text; locations as 6-char geohash.
- `jsonb` only for schemaless payloads (raw records, model output, config, specs) — never for joins/filters.
- Every constraint, index and FK is named predictably (`<table>_<cols>_key|fkey`, `_chkN`, `_iN_idx`, `_uN_uidx`)
  so application errors can be mapped to user messages.
- Every FK has a deliberate `ON DELETE` (§12); `RESTRICT` by default, `CASCADE` only for rows meaningless without
  their parent. FK columns without a covering index get one automatically.

## 3. Domain map

| # | Domain | Tables | Core | Role |
|---|---|---|---|---|
| 1 | Identity & Access | 7 | 5 | In-house auth (email+password, Google OAuth), sessions, tokens/OTP, levels, trust score |
| 2 | Product Catalogue | 7 | 6 | Canonical registry, aliases (dedupe backbone), brands, manufacturers, categories |
| 3 | Media & AI Recognition | 6 | 3 | Content-addressed blobs, owned assets, identification requests, annotations, embeddings |
| 4 | Sources, Ingestion & Evidence | 5 | 4 | Source registry, ingestion jobs, raw versioned records, unified evidence, traceability |
| 5 | Recalls | 5 | 4 | Recall notices, regions, recalled products & identifiers, embeddings |
| 6 | Certifications | 3 | 3 | Schemes, product certificates, check history |
| 7 | Screening, Hazard & Passport | 10 | 4 | Screening runs + candidates, configurable hazard scoring, versioned passports + evidence |
| 8 | Digital Wallet | 6 | 4 | Wallet items, labels, video verification, QR labels, watches |
| 9 | Rewards (TelCoins) | 12 | 0 | Ledger, balances, rules, levels, redemptions, entitlements, holds, referrals, streaks, badges |
| 10 | Community & Reviews | 10 | 3 | Reviews + votes, posts, comments, reactions, hazard flags, fact reports |
| 11 | Commerce Feed | 5 | 0 | Feed items, topics, search history, interactions |
| 12 | Pricing | 2 | 0 | Price snapshots, price alerts |
| 13 | Risk Events & Notifications | 6 | 0 | Product-level risk events, per-user timeline alerts, notifications, devices |
| 14 | Platform, Audit & Ops | 6 | 2 | Settings, audit log, review queue, AI invocation costs, outbox, feature flags |

## 4. Key design decisions

**D1 — One canonical product, many aliases; merge, never delete.** Every external identifier lives in
`product_aliases` with a global `UNIQUE (alias_type, namespace, alias_value)`: a GTIN (normalised to 14
digits, `CHECK`ed) or a namespaced marketplace ID (`amazon.us`, `ebay.us`, `bestbuy`) can never resolve to
two products. A second guard is `UNIQUE (brand_id, model_number_normalized)` for active products with a known
brand. *Deliberately not* extended to unknown brands (`NULLS NOT DISTINCT`): two unbranded products with model
"1000" are not evidence of the same product. Duplicates found later are merged by
`telcron_merge_products(src, dst)` — aliases, media, wallet items, reviews, certificates (and later-phase rows)
move to `dst`; history stays with `src`; merge chains are impossible (trigger) and old links keep resolving.

**D2 — One typed evidence model.** `evidence_items` is a single citable unit whose `kind` dictates exactly
which subject column is set (`CASE kind … END` CHECK): recall (+ optionally the pinned `source_record` version,
so re-syncs never change what was cited), certification check, source record, image region (`bbox`), review,
hazard flag, or web document. `url`/`excerpt` are attributes, not subjects. Passports, hazard dimensions and
traceability link to it through join tables, so one citation renderer serves the whole product.

**D3 — Append-only history, enforced by the database.** `screenings`, `screening_matches`, `passports`,
`passport_evidence`, `certification_checks`, `evidence_items`, `source_records`, `hazard_*`, `coin_ledger_entries`,
`trust_score_events`, `auth_events`, `audit_log` and other logs carry a guard trigger: `DELETE` is refused and
`UPDATE` may only touch an explicit allow-list (e.g. a screening's completion fields, once; a ledger entry's
status). A passport change is a **new version** (`UNIQUE (product_id, version)`, sequenced by trigger). Purges
(account deletion, retention) use a transaction-local `telcron.allow_purge` flag.

**D4 — "Current" pointers are cached, but can't lie.** `products.current_passport_id`,
`product_certifications.current_status / last_check_id`, `reviews.helpful_count`, `posts.*_count` and
`coin_balances` are kept in sync **by triggers/functions in the same transaction**. Pointers use **composite FKs**
(`(current_passport_id, id) → passports (id, product_id)`) so a product can only point at its *own* passport,
a passport can only cite its *own* product's screening, and a certificate only its *own* check.

**D5 — Verdicts are cited and time-bound.** A screening with verdict `match`/`near_match` must have a candidate
with that verdict (deferred constraint trigger); `corpus_synced_at` records *as of when* "no match found" holds.
Passport rules (trigger): the cited screening must be completed; a `match` forces badge `recalled`; `recalled`
requires a match/near-match; tier < 2 ⇒ `needs_information`; tier 2 ⇒ screening + trust score present.

**D6 — Certification vocabulary is honest.** `pending | valid | expired | revoked | not_found | not_checked |
lookup_failed`. An unreachable agency is `lookup_failed`, never `not_found`; a scheme without API access
(UL/ETL today) is `is_checkable = false` ⇒ `not_checked`, never a negative finding. Every check is kept.

**D7 — Hazard scoring is configuration, with a hallucination guard.** `scoring_contexts` (safety now,
sustainability/circularity later; alert threshold 80), non-overlapping `scoring_bands` (`EXCLUDE` constraint) and
`hazard_dimensions` (weights; codes namespaced by context) are data. A dimension score must belong to the
assessment's context (composite FKs). `scored` ⇒ at least one citation (deferred trigger); uncited ⇒
`insufficient_data` with `score IS NULL` (CHECK).

**D8 — TelCoins ledger built like a bank ledger.** Writes go only through `coin_earn`, `coin_confirm_due`,
`coin_spend`, `coin_redeem`, `coin_clawback`, `coin_apply_hold`, `coin_resolve_hold`, which lock the user's
`coin_balances` row first — serialising earn/spend per user so the **daily cap (500, in `app_settings`)**,
per-subject limits (5 reviews per product), lifetime limits (one-time bonuses) and balances are race-free.
Idempotency key UNIQUE (no double award), partial UNIQUE on `reverses_entry_id` (no double clawback/refund),
sign CHECKs per entry type, status machine trigger (`pending → confirmed|frozen|reversed`,
`frozen → confirmed|reversed`). Rapid-fire earning (≥ 20 in 5 min, configurable) opens a fraud hold and freezes
coins. **Clawback policy:** a confirmed-and-spent award is clawed back into a negative balance (debt repaid by
future earnings) — spending can never go negative, clawback can. Reward level is derived from lifetime earned;
the level bonus is its own auditable entry.

**D9 — In-house auth, minimal secrets.** `password_hash` nullable (Google-only users). `user_identities` keyed
on the IdP `sub` (never email); link to an existing account only when the IdP says the email is verified.
Refresh tokens rotate within a `family_id`; `family_expires_at` is copied on rotation so the **90-minute absolute
cap cannot slide**; `last_active_at` drives the 20-minute idle timeout (write-throttled); reuse of a rotated token
revokes the family. Tokens and OTPs are stored only as HMAC hashes (server pepper — a bare SHA-256 of a 6-digit
OTP is brute-forceable), single-use, expiring, attempt-capped. Phone numbers are unique **only once verified**
(no squatting). Level ≥ 1 requires verified email **and** phone (CHECK) — Google users verify a phone.
`password_changed_at` invalidates older sessions. Every attempt lands in partitioned `auth_events`.

**D10 — Files are content-addressed; ownership is separate.** `media_blobs` (one per distinct SHA-256: storage
keys, dimensions, moderation, 64-bit pHash split into four indexed 16-bit bands for near-duplicate search) vs
`media_assets` (owner or source, visibility). Two users uploading the same photo share the file but not each
other's privacy settings; moderation, annotations and embeddings run once per file.

**D11 — Risk events are product-level and deduplicated; alerts are per-user.** One `risk_events` row per
(product, cause) — partial UNIQUEs stop the nightly re-screen from re-alerting; per-type CHECKs require the
right cause FK. `telcron_fanout_risk_event()` creates one `user_risk_alerts` row per affected wallet holder /
watcher, idempotently, honouring **recall geography** (region-specific recalls reach only users in that
country/subdivision; users with unknown location are alerted). Risk instances have media and a discussion thread.

**D12 — Config as data.** Settings (quotas, caps, thresholds, session timeouts), categories (ingestion config),
data sources, certification schemes, scoring, earn rules, levels, redemption items, badges, topics, feature
flags — business changes need no deploy.

**D13 — Embeddings per model.** `embedding_models` registers dimensions; a trigger rejects vectors of the wrong
size; `telcron_create_embedding_index(table, model)` builds a partial HNSW index per activated model. Switching
models is a backfill, not a migration. pgvector is used behind a repository interface; OpenSearch remains a
drop-in if the redesigned architecture wants it (NFR-10).

**D14 — High-volume logs are partitioned from day one.** `audit_log`, `auth_events`, `ai_invocations`,
`feed_interactions` are range-partitioned by month (`PK (id, created_at)`), with a DEFAULT partition and
`telcron_create_monthly_partitions()` to run monthly. They have no inbound FKs, so partitioning costs nothing now
and avoids a full rewrite later. Nightly re-screens should persist a screening only when the verdict or
candidate set changes (application rule) to bound growth.

**D15 — Privacy by design.** PII is concentrated in Identity but also exists in `auth_events`
(email attempted, IP), `audit_log` (IP), posts/reviews (coarse geohash only — never exact coordinates) and user
media. `telcron_anonymise_user()` handles all of them: credentials, OAuth links (so the Google account can
re-register), sessions, tokens, wallet, private logs are removed or scrubbed; public contributions stay as
"Deleted user"; media is hidden for object deletion. ID-document images are never stored.

**D16 — Polymorphic references only where justified.** Typed FKs + CHECKs are used almost everywhere. Untyped
`(type, id)` pairs exist only in cross-cutting, write-mostly tables where referential integrity is not needed for
correctness: `audit_log`, `review_tasks`, `ai_invocations`, `trust_score_events`, and the ledger's
`subject_*/reference_*` (integrity comes from the idempotency key).

## 5. Invariants and where they are enforced

| Invariant | Enforcement | Test |
|---|---|---|
| One product per barcode / marketplace ID | `UNIQUE (alias_type, namespace, alias_value)` + GTIN/namespace CHECKs | `test_one_product_per_barcode`, `test_marketplace_ids_are_namespaced` |
| One active product per brand + model | partial UNIQUE | `test_brand_model_unique_but_unknown_brand_allowed` |
| Merges move user-facing data; no chains | `telcron_merge_products`, trigger | `test_merge_moves_everything_users_touch`, `test_no_merge_chains_or_self_merge` |
| Level ≥ 1 ⇒ verified email (phone dropped for now: ADR-006, migration `20261121120000`) | CHECK | `test_level1_requires_a_verified_email` |
| OAuth subject → one user; verified phone → one user | UNIQUE / partial UNIQUE | `test_oauth_subject_…`, `test_phone_unique_only_once_verified` |
| Session cap can't slide; rotation is linked | CHECKs | `test_session_absolute_cap_cannot_slide`, `test_session_rotation_links_replacement` |
| Evidence has exactly the subject its kind requires | `CASE kind` CHECK | `test_evidence_has_exactly_one_typed_subject` |
| History is append-only | guard triggers | `test_*_immutable`, `test_auth_events_are_append_only_and_partitioned` |
| Pointers reference the same parent | composite FKs | `test_product_cannot_point_at_another_products_passport`, `test_passport_cannot_cite_…`, `test_certificate_cannot_point_…` |
| Match verdict is cited; completed screening frozen | deferred trigger, transition trigger | `test_match_verdict_must_cite_a_matching_candidate`, `test_completed_screening_is_frozen` |
| Recall match ⇔ Recalled badge; tier rules; versioning | trigger + CHECKs | `test_recall_match_forces_recalled_badge`, `test_recalled_badge_requires_a_match`, `test_tiers_and_versions` |
| Scored hazard dimension is cited; context-consistent; bands don't overlap | deferred trigger, composite FKs, EXCLUDE | `test_scored_dimension_needs_a_citation`, `test_dimension_must_belong_…`, `test_score_bands_cannot_overlap` |
| Manual/barcode wallet add needs a *matched* video of *that* item | CHECK + composite FK + trigger | `test_manual_add_stays_pending_until_matched_video`, `test_verification_must_belong_…` |
| One active wallet entry / label owner match | partial UNIQUE, trigger | `test_one_active_wallet_entry_…`, `test_labels_are_per_user_…` |
| Coins: no double award / spend / clawback; caps & limits; valid transitions | coin_* functions, UNIQUEs, CHECKs, trigger | `test_rewards.py` (12 tests incl. a real two-connection race) |
| Re-screen never re-alerts; regional recalls reach only that region | partial UNIQUEs, fan-out function | `test_rescreen_does_not_duplicate_risk_events`, `test_regional_recalls_reach_only_that_region` |
| Ingested content is deduplicated by origin | partial UNIQUEs | `test_ingested_reviews_are_keyed_on_source`, `test_feed_items_typed_and_deduplicated` |
| Wallet cap, daily identification quota | application (one indexed count each; values in `app_settings`) | — |

## 6. Main read paths — measured

Measured with `EXPLAIN ANALYZE` on 100k products, 200k aliases, 30k recalls, 150k wallet items, 300k ledger
entries, 150k timeline alerts (`make db-test-perf`). Every path is index-backed; none seq-scans a large table.

| Read path | Time | Index |
|---|---|---|
| Barcode → product | 0.04 ms | `product_aliases (alias_type, namespace, alias_value)` |
| Public passport page (slug → current passport) | 0.05 ms | `products.public_slug`, `passports (id, product_id)` |
| Fuzzy product search, top-10 by similarity | ~7–17 ms | GiST `gist_trgm_ops(siglen=64)` KNN (`ORDER BY name <-> q`) |
| Recall full-text search | 0.06 ms | GIN `recalls.search_tsv` |
| Recall by exact model identifier | 0.03 ms | `recall_product_identifiers (identifier_type, value_normalized)` |
| Fuzzy recall-product candidates | 3.4 ms | GiST trigram KNN on `recall_products.product_name` |
| Product by model number (new-recall reverse match) | 0.03 ms | `products (model_number_normalized)` |
| New recall → previously screened products | 0.04 ms | `screening_matches (recall_id)` |
| My wallet | 0.08 ms | `wallet_items (user_id, created_at DESC) WHERE deleted_at IS NULL` |
| Wallet holders of a product (alert fan-out) | 0.03 ms | `wallet_items (product_id) WHERE …alerts_enabled` |
| Risk timeline grouped by day | 0.06 ms | `user_risk_alerts (user_id, created_at DESC)` |
| TelCoins earned today (cap check) | 0.06 ms | `coin_ledger_entries (user_id, created_at DESC)` |
| Feed: country × category, newest | 0.07 ms | `feed_items (country_code, category_id, published_at DESC)` |

The perf test found one design flaw, now fixed: fuzzy search originally used a GIN trigram index, which can
filter but cannot return the *nearest* matches — it fell back to a 299 ms full scan. GiST with KNN ordering
and a longer signature (`siglen=64`, 11 MB at 100k rows) brought it under 20 ms on deliberately repetitive names.

## 7. Phasing

| Phase | Tables | Unlocks | Location |
|---|---|---|---|
| **1 — Core (38)** | Identity (5), Catalogue (6), Media blobs/assets/identification (3), Sources (4), Recalls (4), Certifications (3), Screening/Passport (4), Wallet + video verification (4), Reviews (3), `app_settings`, `audit_log` | Sign-up/login/Google, product page, public passport, recall & certification views, wallet, reviews | `db/migrations/2026111412*` — applied |
| 2 — AI engine (14) | traceability, embeddings + models, annotations, hazard scoring (6), review queue, AI invocations, outbox | Identification/scoring pipeline, ingestion evidence, re-screen fan-out | `db/migrations/20261122130000_phase2_schema.sql` + `…130100_phase2_rules.sql` — applied (WO-022) |
| 3 — Engagement (38) | Rewards (12), Community (7 more), Feed (5), Pricing (2), Risk & notifications (6), wallet extras, identity extras, product variants, feature flags | TelCoins, community feed, commerce feed, price alerts, risk timeline | `db/migrations/20261122130200_phase3_schema.sql` + `…130300_phase3_rules.sql` — applied (WO-022) |

FKs are emitted in the phase where both ends exist (e.g. `passports.hazard_assessment_id`'s constraint arrives
with phase 2).

Phases 2–3 were promoted to dbmate migrations on 2026-11-22 (WO-022, decision D11). Before that they were
applied outside dbmate (`make db-next` locally, a hand-written block on the AWS dev host), so each promoted
migration is one guarded block that **skips, without error, a database that already has the phase**: the
schema migrations are keyed on `hazard_assessments` / `coin_ledger_entries`, the rules on
`telcron_dimension_score_cited()` / `coin_earn()`. A database holding only part of a phase fails loudly
instead of being half-patched. Their reference rows are `20261122130400_phase2_3_reference.sql`
(idempotent). `make db-gen` regenerates the two schema migrations from the spec; the rules and the
reference rows are hand-written. A fresh database is `dbmate up` + `db/seeds/001_core_reference.sql`; there
is no other step (`make db-next` is retired).

## 8. Feature traceability

| Feature | Tables |
|---|---|
| TC-P1-001/002 Registration, login, reset | `users`, `user_identities`, `sessions`, `verification_tokens`, `auth_events`, `identity_verifications` |
| TC-P1-003 Upload & AI identify | `media_blobs`, `media_assets`, `identification_requests`, `products`, `product_media` |
| TC-P1-004 Visual-search gallery | `feed_items`, `media_assets`, `data_sources` |
| TC-P1-005 Ingestion & filtering | `data_sources`, `ingestion_jobs`, `source_records`, `categories` |
| TC-P1-006 Image processing & index | `media_blobs` (hash, EXIF, moderation, pHash), `media_embeddings`, `embedding_models` |
| TC-P1-007 AI feed, tabs, filters, labels | `feed_items`, `feed_item_topics`, `topics`, `feed_interactions`, `search_queries` |
| TC-P1-008 Traceability & evidence | `product_aliases`, `manufacturers`, `products.traceability_status`, `product_traceability`, `evidence_items` |
| TC-P1-009 Certifications & history | `certification_schemes`, `product_certifications`, `certification_checks`, `review_tasks` (manual review) |
| TC-P1-010 Recall lookup & alerts | `recalls`, `recall_regions`, `recall_products`, `recall_product_identifiers`, `screenings`, `risk_events` |
| TC-P1-011/012 Hazard scoring & contract | `scoring_contexts`, `scoring_bands`, `hazard_dimensions`, `hazard_assessments`, `hazard_dimension_scores`, `hazard_score_citations` |
| TC-P1-013/014/015 Wallet, video check, QR | `wallet_items`, `wallet_labels`, `wallet_item_labels`, `wallet_item_verifications`, `qr_labels` |
| TC-P1-016/017/018 Rewards | `coin_*`, `reward_levels`, `redemption_items`, `redemptions`, `user_entitlements`, `fraud_holds`, `referrals`, `user_daily_logins`, `badges`, `user_badges`, `product_watches`, `feature_flags` |
| TC-P1-019 Real-time annotation | `media_annotations` |
| TC-P1-020 Chrome extension | no own tables — consumes identify/passport APIs (`wallet_items.add_method = 'extension'`) |
| TC-P1-021…025 Community | `posts`, `post_media`, `reviews`, `review_media`, `review_votes`, `hazard_flags`, `hazard_flag_media`, `comments`, `reactions`, `product_fact_reports`, view `community_feed` |
| TC-P1-024 Price alerts | `price_snapshots`, `price_alerts` |
| TC-P1-026 Account (referral, profile) | `users`, `referrals` |
| TC-P1-029 Risk timeline | `risk_events`, `risk_event_media`, `user_risk_alerts`, `comments`, `notifications` |
| Month-1 Passport (FR-01…17) | Catalogue + Media + Recalls + Certifications + Screening/Passport + `audit_log` |

## 9. Review history

v0.1 was drafted from the requirements, then an **independent reviewer agent** audited it against Feature List V2
without seeing the author's conclusions (3 critical, 16 major, ~12 minor findings). v0.2 resolves them:

| Finding | Resolution |
|---|---|
| C1 pointers could reference another product's rows | Composite FKs on every "current"/cited pointer (D4) |
| C2 uncited verdicts/scores possible | Deferred constraint triggers (D5, D7) |
| C3 ledger CHECKs contradictory; double clawback; clawback vs non-negative balance; unconstrained transitions; cap not stored | Rewritten CHECKs, partial UNIQUE, debt policy, transition trigger, `app_settings` cap, locking functions (D8) |
| M1 re-screens re-alert daily | Partial UNIQUEs on `risk_events` + per-type CHECKs (D11) |
| M2 evidence too narrow; recall citations drift | Review/hazard-flag subjects, pinned source record, `url` as attribute (D2) |
| M3 dedupe vs ownership; pHash not searchable | `media_blobs` / `media_assets` split; banded pHash (D10) |
| M4 duplicates, merge chains, merge procedure | Merge function + trigger. *Not adopted:* `NULLS NOT DISTINCT` for unknown brands (see D1) |
| M5 re-ingestion duplicates content | Natural-key partial UNIQUEs on reviews and feed items |
| M6 sliding session cap, token lookup, OTP hashing, phone squatting | `family_expires_at`, UNIQUE token hash, HMAC, partial phone UNIQUE (D9) |
| M7 certification states missing | `pending`, `lookup_failed`; review-task submitter + payload (D6) |
| M8 wallet video rule unenforced | CHECK + composite FK + trigger; no default status |
| M9 risk-timeline thread, media, time zone | `comments.risk_event_id`, `risk_event_media`, `users.time_zone` |
| M10 untraceable outcome | `products.traceability_status` |
| M11 reverse match & recall geography | `products (model_number_normalized)` index; `users.subdivision_code`; geographic fan-out |
| M12 exact public locations; PII outside identity | Geohash-6 only; full anonymisation function (D15) |
| M13 constraints written as prose | Every CHECK/UNIQUE/index is now literal SQL, compiled and tested |
| M14 contradictory ON DELETE | Reviewer FKs are `RESTRICT` |
| M15 append-only vs updates; late partitioning | Allow-listed guard (D3); log partitioning now (D14) |
| M16 community location filter | `geohash` on reviews and hazard flags |
| Minor | `reward_levels` rename, `score_after` on trust events, entitlement sources, badges, `embedding_models`, FK covering indexes, redundant columns removed (`referred_by_user_id`, `locked` status, `price_alerts.user_id`) |

Testing then found two more defects the review had not: the append-only guard silently passed on insert-only
tables (Postgres passes `NULL`, not `{}`, as trigger args) and the fuzzy-search index choice (§6). Both fixed.

## 10. Testing

`make db-test` — 66 tests in ~2 s on a throwaway in-memory Postgres 18 built from the **real migration files**:
identity & auth (10), catalogue & media (8), evidence/certification/screening/passport/hazard (18),
wallet & community (10), TelCoins incl. a two-connection double-spend race (12), risk/feed/pricing (8).
Each test runs in a rolled-back transaction; deferred constraints are checked with `SET CONSTRAINTS ALL IMMEDIATE`.

`make db-test-perf` — loads ~1.3 M rows and asserts each read path in §6 is index-backed and < 25 ms (~1 min).

Migrations are also verified to roll back cleanly to an empty database and re-apply.

## 11. Open questions (business / team decisions)

| # | Question | Default used |
|---|---|---|
| Q1 | Reviews per user per product: one (edit instead), or several? Coins are capped at 5 reviews/product (TC-P1-016) | Several allowed; coins capped at 5 per product |
| Q2 | Rating scale 1–5 (TC-P1-022 marks it unconfirmed) | 1–5 |
| Q3 | Trust Score formula & badge bands (D-07) | Components stored; `formula_version` column |
| Q4 | Hazard bands (Low < 30 ≤ Medium < 60 ≤ High) **and** alert threshold 80 — keep both? | Both, configurable |
| Q5 | Wallet cap 100 still valid? | `app_settings wallet.max_items = 100` |
| Q6 | Embedding model(s) and pgvector vs OpenSearch in the redesigned architecture | pgvector behind an interface; Titan v2 (1024) registered as active |
| Q7 | Retention for logs, screenings and media; deletion SLA | Logs partitioned monthly (retention = drop old partitions); history kept |
| Q8 | Business accounts (Level 3): organisations, API keys | Not modelled yet; `verification_level` allows 3 |
| Q9 | Clawback into negative balance (debt) acceptable? | Yes (D8) |
| Q10 | Multi-currency price alerts | Alert currency must match snapshot currency |

## 12. Table catalogue

Generated from `schema_spec.py` — do not edit by hand.

<!-- CATALOGUE:START -->

### Identity & Access

#### `users` — ★ core · phase 1

One row per person. Holds account PII. Password optional (OAuth-only users). Deletion = anonymise.  
*Serves:* TC-P1-001/002/026, FR-14

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `email` | citext |  | UK |  |  |
| `email_verified_at` | timestamptz | yes |  |  |  |
| `phone_e164` | text | yes |  |  | E.164; unique once verified |
| `phone_verified_at` | timestamptz | yes |  |  |  |
| `password_hash` | text | yes |  |  | argon2id; NULL for OAuth-only accounts |
| `password_changed_at` | timestamptz | yes |  |  | sessions issued before this are invalid |
| `display_name` | text |  |  |  |  |
| `avatar_media_id` | uuid → `media_assets.id` (set null) | yes | FK |  |  |
| `country_code` | char(2) | yes |  |  | ISO-3166-1 |
| `subdivision_code` | text | yes |  |  | ISO-3166-2 — regional recall applicability |
| `locale` | text |  |  | `'en'` |  |
| `time_zone` | text |  |  | `'UTC'` | IANA; risk-timeline day grouping |
| `status` | user_status |  |  | `'pending'` |  |
| `role` | user_role |  |  | `'user'` |  |
| `verification_level` | smallint |  |  | `0` | 0 pending · 1 basic · 2 full · 3 business |
| `trust_score` | numeric(5,2) |  |  | `0` | = latest trust_score_events.score_after |
| `referral_code` | text |  | UK |  |  |
| `failed_login_count` | smallint |  |  | `0` |  |
| `locked_until` | timestamptz | yes |  |  |  |
| `last_login_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |
| `deleted_at` | timestamptz | yes |  |  | soft delete |

**Unique:** `UNIQUE (phone_e164) WHERE phone_verified_at IS NOT NULL`  
**Checks:** `verification_level BETWEEN 0 AND 3`; `trust_score BETWEEN 0 AND 100`; `verification_level = 0 OR email_verified_at IS NOT NULL`; `phone_verified_at IS NULL OR phone_e164 IS NOT NULL`; `phone_e164 IS NULL OR phone_e164 ~ '^\+[1-9][0-9]{6,14}$'`; `(status = 'deleted') = (deleted_at IS NOT NULL)`  
**Indexes:** `(status) WHERE deleted_at IS NULL`

#### `user_identities` — ★ core · phase 1

OAuth identities linked to a user, keyed on the IdP's stable subject (never the email).  
*Serves:* TC-P1-001/002

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `provider` | auth_provider |  |  |  |  |
| `provider_subject` | text |  |  |  |  |
| `provider_email` | citext | yes |  |  |  |
| `provider_email_verified` | boolean |  |  | `false` |  |
| `last_used_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (provider, provider_subject)`; `UNIQUE (user_id, provider)`  
**Rules (triggers/functions):** Link to an existing email account only when provider_email_verified (app).

#### `sessions` — ★ core · phase 1

Refresh-token sessions with rotation. family_expires_at = 90-min absolute cap (never slides); last_active_at = 20-min idle.  
*Serves:* TC-P1-002

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `family_id` | uuid |  |  |  | all rotations of one login |
| `refresh_token_hash` | bytea |  | UK |  | SHA-256 of a 256-bit random token |
| `family_expires_at` | timestamptz |  |  |  | copied unchanged on rotation |
| `expires_at` | timestamptz |  |  |  |  |
| `last_active_at` | timestamptz |  |  | `now()` | write-throttled (≥1 min) |
| `rotated_at` | timestamptz | yes |  |  |  |
| `replaced_by_session_id` | uuid → `sessions.id` (set null) | yes | FK |  |  |
| `ip_address` | inet | yes |  |  |  |
| `user_agent` | text | yes |  |  |  |
| `revoked_at` | timestamptz | yes |  |  |  |
| `revoke_reason` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Rules (triggers/functions):** Presenting a rotated token ⇒ revoke whole family + auth_event token_reuse_detected (app).  
**Checks:** `expires_at <= family_expires_at`; `(rotated_at IS NULL) = (replaced_by_session_id IS NULL)`  
**Indexes:** `(user_id) WHERE revoked_at IS NULL`; `(family_id)`

#### `verification_tokens` — ★ core · phase 1

Single-use email links, phone OTPs, password-reset tokens: hashed (OTPs HMAC-peppered), expiring, attempt-limited.  
*Serves:* TC-P1-001/002

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `purpose` | token_purpose |  |  |  |  |
| `target` | text |  |  |  | email or phone being verified |
| `token_hash` | bytea |  | UK |  | HMAC-SHA256(server pepper, token) |
| `attempt_count` | smallint |  |  | `0` |  |
| `expires_at` | timestamptz |  |  |  |  |
| `consumed_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `attempt_count BETWEEN 0 AND 10`; `expires_at > created_at`  
**Indexes:** `(user_id, purpose) WHERE consumed_at IS NULL`

#### `auth_events` — ★ core · append-only · phase 1

Every authentication attempt/event, success or failure. Drives lockout and rate limiting. Monthly partitions.  
*Serves:* TC-P1-002

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid | yes |  |  | no FK — log survives account deletion (anonymised) |
| `event_type` | auth_event_type |  |  |  |  |
| `email_attempted` | citext | yes |  |  |  |
| `provider` | auth_provider | yes |  |  |  |
| `failure_reason` | text | yes |  |  |  |
| `ip_address` | inet | yes |  |  |  |
| `user_agent` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Partitioned:** monthly by `created_at` (PK includes it)  
**Append-only:** insert-only  
**Indexes:** `(user_id, created_at DESC)`; `(ip_address, created_at DESC)`; `(email_attempted, created_at DESC)`

#### `identity_verifications` — phase 3

Outcome of ID-document OCR + selfie face-match. Result only — images are deleted after the check.  
*Serves:* TC-P1-001 (Level 2)

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `document_type` | text | yes |  |  |  |
| `document_country` | char(2) | yes |  |  |  |
| `status` | identity_check_status |  |  | `'pending'` |  |
| `ocr_succeeded` | boolean | yes |  |  |  |
| `face_match_score` | numeric(5,4) | yes |  |  |  |
| `failure_reason` | text | yes |  |  |  |
| `provider` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `completed_at` | timestamptz | yes |  |  |  |

**Checks:** `status = 'pending' OR completed_at IS NOT NULL`; `status <> 'passed' OR (ocr_succeeded AND face_match_score IS NOT NULL)`  
**Indexes:** `(user_id, created_at DESC)`

#### `trust_score_events` — append-only · phase 3

Every trust-score change with reason and resulting score (score is clamped and can be set, so the result is stored).  
*Serves:* Arch v2 §5.4

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `delta` | numeric(5,2) |  |  |  |  |
| `score_after` | numeric(5,2) |  |  |  |  |
| `reason_code` | text |  |  |  | review_helpful, spam_report, flag_confirmed, level2_baseline… |
| `reference_type` | text | yes |  |  |  |
| `reference_id` | uuid | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Append-only:** insert-only  
**Checks:** `score_after BETWEEN 0 AND 100`  
**Indexes:** `(user_id, created_at DESC)`


### Product Catalogue (Registry)

#### `categories` — ★ core · phase 1

Hierarchical categories; new categories onboard by configuration.  
*Serves:* TC-P1-005, NFR-10

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `parent_id` | uuid → `categories.id` (restrict) | yes | FK |  |  |
| `code` | text |  | UK |  |  |
| `name` | text |  |  |  |  |
| `is_active` | boolean |  |  | `true` |  |
| `config` | jsonb |  |  | `'{}'` | ingestion queries, image counts, visual hazard signals |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Checks:** `parent_id IS NULL OR parent_id <> id`; `code ~ '^[a-z0-9_]+$'`

#### `manufacturers` — ★ core · phase 1

Legal manufacturer resolved by traceability (may differ from the consumer brand).  
*Serves:* TC-P1-008

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `name` | text |  |  |  |  |
| `normalized_name` | text |  | UK |  |  |
| `country_code` | char(2) | yes |  |  |  |
| `website_url` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Indexes:** `gin (normalized_name gin_trgm_ops)`

#### `brands` — ★ core · phase 1

Consumer-facing brand marks; optionally owned by a manufacturer.

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `name` | text |  |  |  |  |
| `normalized_name` | text |  | UK |  |  |
| `manufacturer_id` | uuid → `manufacturers.id` (set null) | yes | FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Indexes:** `gin (normalized_name gin_trgm_ops)`

#### `products` — ★ core · phase 1

Canonical Product Identity Registry record. Never hard-deleted; duplicates are merged.  
*Serves:* FR-04/05, TC-P1-005/008, Arch v2 §4

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `category_id` | uuid → `categories.id` (restrict) |  | FK |  |  |
| `brand_id` | uuid → `brands.id` (restrict) | yes | FK |  |  |
| `manufacturer_id` | uuid → `manufacturers.id` (restrict) | yes | FK |  |  |
| `canonical_name` | text |  |  |  |  |
| `model_number` | text | yes |  |  |  |
| `model_number_normalized` | text | yes |  |  | upper-case alphanumerics |
| `description` | text | yes |  |  |  |
| `specifications` | jsonb |  |  | `'{}'` | current values; provenance in product_traceability |
| `status` | product_status |  |  | `'active'` |  |
| `merged_into_product_id` | uuid → `products.id` (restrict) | yes | FK |  |  |
| `identification_source` | identification_source |  |  |  |  |
| `identity_confidence` | numeric(4,3) | yes |  |  |  |
| `traceability_status` | traceability_status |  |  | `'pending'` |  |
| `traceability_checked_at` | timestamptz | yes |  |  |  |
| `primary_media_id` | uuid → `media_assets.id` (set null) | yes | FK |  |  |
| `current_passport_id` | uuid → `passports.id` (restrict) | yes | FK |  | composite FK ⇒ must be THIS product's passport |
| `public_slug` | text |  | UK |  |  |
| `created_by_user_id` | uuid → `users.id` (set null) | yes | FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (brand_id, model_number_normalized) WHERE model_number_normalized IS NOT NULL AND brand_id IS NOT NULL AND status <> 'merged'`  
**Composite FKs:** `(current_passport_id, id) → passports(id, product_id)` deferrable  
**Rules (triggers/functions):** Merge target may not itself be merged (trigger). merge_products(src, dst) moves aliases, media, wallet items, reviews (function).  
**Checks:** `(status = 'merged') = (merged_into_product_id IS NOT NULL)`; `merged_into_product_id IS NULL OR merged_into_product_id <> id`; `identity_confidence BETWEEN 0 AND 1`; `public_slug ~ '^[a-z0-9-]{6,80}$'`; `model_number_normalized IS NULL OR model_number_normalized ~ '^[A-Z0-9]+$'`  
**Indexes:** `gist (canonical_name gist_trgm_ops(siglen=64))`; `(model_number_normalized)`; `(category_id, status)`

#### `product_variants` — phase 3

Colour / size / pack variants of one canonical product.  
*Serves:* Arch v2 §4.2

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (cascade) |  | FK |  |  |
| `name` | text |  |  |  |  |
| `attributes` | jsonb |  |  | `'{}'` |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (product_id, name)`

#### `product_aliases` — ★ core · phase 1

External identifiers resolving to ONE canonical product — the dedupe backbone. GTINs are global; marketplace IDs are namespaced (amazon.us, ebay.us, bestbuy…).  
*Serves:* FR-04, TC-P1-008

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (cascade) |  | FK |  |  |
| `variant_id` | uuid → `product_variants.id` (set null) | yes | FK |  |  |
| `alias_type` | alias_type |  |  |  |  |
| `namespace` | text |  |  | `''` |  |
| `alias_value` | text |  |  |  | GTIN normalised to 14 digits |
| `data_source_code` | text → `data_sources.code` (restrict) | yes | FK |  |  |
| `confidence` | numeric(4,3) | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (alias_type, namespace, alias_value)`  
**Checks:** `(alias_type = 'gtin') = (namespace = '')`; `alias_type <> 'gtin' OR alias_value ~ '^[0-9]{14}$'`; `confidence BETWEEN 0 AND 1`

#### `product_media` — ★ core · phase 1

Which media assets illustrate a product, and in what role.  
*Serves:* TC-P1-006

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `product_id` | uuid → `products.id` (cascade) |  | PK FK |  |  |
| `media_asset_id` | uuid → `media_assets.id` (cascade) |  | PK FK |  |  |
| `role` | media_role |  |  | `'gallery'` |  |
| `sort_order` | smallint |  |  | `0` |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(product_id, media_asset_id)`

#### `product_embeddings` — phase 2

Semantic vector of a product's identity and known safety facts, per model.  
*Serves:* WO-015 semantic search, similar products, assistant retrieval

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `product_id` | uuid → `products.id` (cascade) |  | PK FK |  |  |
| `model_code` | text → `embedding_models.code` (restrict) |  | PK FK |  |  |
| `content_sha256` | bytea |  |  |  | re-embed only when the text changes |
| `embedding` | vector |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(product_id, model_code)`


### Media & AI Recognition

#### `media_blobs` — ★ core · phase 1

Content-addressed file (one per distinct bytes): storage keys, hashes, dimensions, moderation. Shared by every asset with the same content.  
*Serves:* TC-P1-006, NFR-04

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `sha256` | bytea |  | UK |  |  |
| `kind` | media_kind |  |  |  |  |
| `mime_type` | text |  |  |  |  |
| `byte_size` | bigint |  |  |  |  |
| `width` | integer | yes |  |  |  |
| `height` | integer | yes |  |  |  |
| `duration_ms` | integer | yes |  |  |  |
| `storage_key_original` | text |  |  |  |  |
| `storage_key_normalized` | text | yes |  |  | ≤1024px JPEG, EXIF stripped |
| `perceptual_hash` | bigint | yes |  |  | 64-bit pHash |
| `phash_band0` | integer | yes |  |  |  |
| `phash_band1` | integer | yes |  |  |  |
| `phash_band2` | integer | yes |  |  |  |
| `phash_band3` | integer | yes |  |  |  |
| `moderation_status` | moderation_status |  |  | `'pending'` |  |
| `moderation_labels` | jsonb | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Rules (triggers/functions):** Near-duplicate = any band equal, then bit_count((a # b)::bit(64)) <= threshold.  
**Checks:** `byte_size > 0`; `(kind = 'video') = (duration_ms IS NOT NULL)`; `octet_length(sha256) = 32`  
**Indexes:** `(phash_band0)`; `(phash_band1)`; `(phash_band2)`; `(phash_band3)`

#### `media_assets` — ★ core · phase 1

A use of a blob by an owner (user upload) or source (ingested): ownership and visibility live here, not on the file.  
*Serves:* TC-P1-003/006

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `blob_id` | uuid → `media_blobs.id` (restrict) |  | FK |  |  |
| `owner_user_id` | uuid → `users.id` (set null) | yes | FK |  |  |
| `data_source_code` | text → `data_sources.code` (restrict) | yes | FK |  |  |
| `visibility` | visibility |  |  | `'private'` |  |
| `caption` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `deleted_at` | timestamptz | yes |  |  | soft delete |

**Unique:** `UNIQUE (owner_user_id, blob_id) WHERE owner_user_id IS NOT NULL AND deleted_at IS NULL`  
**Checks:** `num_nonnulls(owner_user_id, data_source_code) >= 1`  
**Indexes:** `(owner_user_id, created_at DESC)`

#### `media_annotations` — phase 2

AI labels on a file (label, confidence, bbox, video frame), optionally resolved to a product.  
*Serves:* TC-P1-019

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `blob_id` | uuid → `media_blobs.id` (cascade) |  | FK |  |  |
| `label` | text |  |  |  |  |
| `confidence` | numeric(4,3) |  |  |  |  |
| `bbox` | int4[] | yes |  |  | [x, y, w, h] px |
| `frame_ms` | integer | yes |  |  |  |
| `product_id` | uuid → `products.id` (set null) | yes | FK |  |  |
| `model_code` | text |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `bbox IS NULL OR cardinality(bbox) = 4`; `confidence BETWEEN 0 AND 1`

#### `embedding_models` — phase 2

Registry of embedding models and their dimensions (CLIP ViT-L/14 = 768, Titan v2 = 1024…).  
*Serves:* TC-P1-006, D-05

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `modality` | embedding_modality |  |  |  |  |
| `dimensions` | integer |  |  |  |  |
| `is_active` | boolean |  |  | `false` |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `dimensions BETWEEN 1 AND 16000`

#### `media_embeddings` — phase 2

Image embeddings per model for visual similarity search.  
*Serves:* TC-P1-006

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `blob_id` | uuid → `media_blobs.id` (cascade) |  | PK FK |  |  |
| `model_code` | text → `embedding_models.code` (restrict) |  | PK FK |  |  |
| `embedding` | vector |  |  |  | dims checked against embedding_models (trigger) |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(blob_id, model_code)`  
**Rules (triggers/functions):** HNSW index per active model: ((embedding::vector(N)) vector_cosine_ops) WHERE model_code = '…' — created when a model is activated.

#### `identification_requests` — ★ core · phase 1

Each capture → identify attempt (Tier 0/1): input, model output, confidence, escalation, fallback answers.  
*Serves:* FR-01/02/03/05, TC-P1-003

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (set null) | yes | FK |  |  |
| `input_type` | capture_input |  |  |  |  |
| `media_asset_id` | uuid → `media_assets.id` (restrict) | yes | FK |  |  |
| `barcode_value` | text | yes |  |  |  |
| `text_query` | text | yes |  |  |  |
| `status` | identification_status |  |  | `'pending'` |  |
| `extracted` | jsonb | yes |  |  | {product_type, brand, model, evidence_snippets} |
| `confidence` | numeric(4,3) | yes |  |  |  |
| `escalated` | boolean |  |  | `false` |  |
| `fallback_manufacturer` | text | yes |  |  |  |
| `fallback_model` | text | yes |  |  |  |
| `resolved_product_id` | uuid → `products.id` (restrict) | yes | FK |  |  |
| `cache_hit` | boolean |  |  | `false` |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `completed_at` | timestamptz | yes |  |  |  |

**Checks:** `num_nonnulls(media_asset_id, barcode_value, text_query) >= 1`; `input_type NOT IN ('image','video') OR media_asset_id IS NOT NULL`; `input_type <> 'barcode' OR barcode_value IS NOT NULL`; `input_type <> 'text' OR text_query IS NOT NULL`; `status <> 'identified' OR resolved_product_id IS NOT NULL`; `confidence BETWEEN 0 AND 1`  
**Indexes:** `(user_id, created_at DESC)`


### Sources, Ingestion & Evidence

#### `data_sources` — ★ core · phase 1

Registry of every source (CPSC, openFDA, FCC, Energy Star, Amazon, eBay, Best Buy, user uploads…).  
*Serves:* TC-P1-004/005, D-01

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `name` | text |  |  |  |  |
| `kind` | data_source_kind |  |  |  |  |
| `base_url` | text | yes |  |  |  |
| `country_codes` | char(2)[] |  |  | `'{}'` |  |
| `is_enabled` | boolean |  |  | `true` |  |
| `config` | jsonb |  |  | `'{}'` | rate limits, schedule — never secrets |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Checks:** `code ~ '^[a-z0-9_.]+$'`

#### `ingestion_jobs` — ★ core · phase 1

One run of a sync/ingestion pipeline with stats and errors.  
*Serves:* TC-P1-005, RCL-01

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `data_source_code` | text → `data_sources.code` (restrict) |  | FK |  |  |
| `category_id` | uuid → `categories.id` (restrict) | yes | FK |  |  |
| `trigger` | job_trigger |  |  |  |  |
| `status` | job_status |  |  | `'queued'` |  |
| `params` | jsonb |  |  | `'{}'` |  |
| `stats` | jsonb |  |  | `'{}'` |  |
| `error` | text | yes |  |  |  |
| `triggered_by_user_id` | uuid → `users.id` (set null) | yes | FK |  |  |
| `started_at` | timestamptz | yes |  |  |  |
| `finished_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `finished_at IS NULL OR started_at IS NOT NULL`  
**Indexes:** `(data_source_code, created_at DESC)`

#### `source_records` — ★ core · append-only · phase 1

Raw payload of every fetched external record, versioned by content hash — reprocess without re-fetching.  
*Serves:* Arch v2 §10, TC-P1-008

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `data_source_code` | text → `data_sources.code` (restrict) |  | FK |  |  |
| `record_type` | source_record_type |  |  |  |  |
| `external_id` | text |  |  |  |  |
| `payload` | jsonb | yes |  |  |  |
| `payload_storage_key` | text | yes |  |  |  |
| `payload_sha256` | bytea |  |  |  |  |
| `ingestion_job_id` | uuid → `ingestion_jobs.id` (restrict) | yes | FK |  |  |
| `fetched_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (data_source_code, record_type, external_id, payload_sha256)`  
**Append-only:** insert-only  
**Checks:** `num_nonnulls(payload, payload_storage_key) = 1`  
**Indexes:** `(data_source_code, record_type, external_id, fetched_at DESC)`

#### `evidence_items` — ★ core · append-only · phase 1

One citable piece of evidence with exactly one typed subject; recall citations also pin the source-record version.  
*Serves:* P3 zero-unvetted-data, TC-P1-008/011

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `kind` | evidence_kind |  |  |  |  |
| `recall_id` | uuid → `recalls.id` (restrict) | yes | FK |  |  |
| `certification_check_id` | uuid → `certification_checks.id` (restrict) | yes | FK |  |  |
| `source_record_id` | uuid → `source_records.id` (restrict) | yes | FK |  | pinned version (also allowed with recall) |
| `media_asset_id` | uuid → `media_assets.id` (restrict) | yes | FK |  |  |
| `review_id` | uuid → `reviews.id` (restrict) | yes | FK |  |  |
| `hazard_flag_id` | uuid → `hazard_flags.id` (restrict) | yes | FK |  |  |
| `bbox` | int4[] | yes |  |  | [x, y, w, h] px |
| `url` | text | yes |  |  | display/link attribute, not a subject |
| `excerpt` | text | yes |  |  | quoted chunk cited by the model |
| `created_at` | timestamptz |  |  | `now()` |  |

**Append-only:** insert-only  
**Checks:** `bbox IS NULL OR (kind = 'media_region' AND cardinality(bbox) = 4)`; `CASE kind WHEN 'recall' THEN recall_id IS NOT NULL AND num_nonnulls(certification_check_id, media_asset_id, review_id, hazard_flag_id) = 0 WHEN 'certification_check' THEN certification_check_id IS NOT NULL AND num_nonnulls(recall_id, media_asset_id, review_id, hazard_flag_id) = 0 WHEN 'source_record' THEN source_record_id IS NOT NULL AND num_nonnulls(recall_id, certification_check_id, media_asset_id, review_id, hazard_flag_id) = 0 WHEN 'media_region' THEN media_asset_id IS NOT NULL AND num_nonnulls(recall_id, certification_check_id, source_record_id, review_id, hazard_flag_id) = 0 WHEN 'review' THEN review_id IS NOT NULL AND num_nonnulls(recall_id, certification_check_id, source_record_id, media_asset_id, hazard_flag_id) = 0 WHEN 'hazard_flag' THEN hazard_flag_id IS NOT NULL AND num_nonnulls(recall_id, certification_check_id, source_record_id, media_asset_id, review_id) = 0 WHEN 'web_document' THEN url IS NOT NULL AND num_nonnulls(recall_id, certification_check_id, source_record_id, media_asset_id, review_id, hazard_flag_id) = 0 END`

#### `product_traceability` — phase 2

Resolved product facts (manufacturer, model, specs) with evidence and method — the permanent 'why we believe this'.  
*Serves:* TC-P1-008

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (cascade) |  | FK |  |  |
| `attribute` | text |  |  |  | manufacturer | model | spec:<key> |
| `value` | text |  |  |  |  |
| `evidence_id` | uuid → `evidence_items.id` (restrict) |  | FK |  |  |
| `match_method` | text |  |  |  | gtin_exact | brand_model | ai_assisted |
| `confidence` | numeric(4,3) | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Indexes:** `(product_id, attribute)`

#### `evidence_embeddings` — phase 2

Semantic vector of one evidence item's excerpt (finding, recall, review, flag), per model.  
*Serves:* WO-015 assistant retrieval

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `evidence_id` | uuid → `evidence_items.id` (cascade) |  | PK FK |  |  |
| `model_code` | text → `embedding_models.code` (restrict) |  | PK FK |  |  |
| `embedding` | vector |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(evidence_id, model_code)`


### Recalls

#### `recalls` — ★ core · phase 1

Official recall notices (CPSC, openFDA; later NHTSA, EU Safety Gate…). Reference data.  
*Serves:* FR-06, TC-P1-010

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `data_source_code` | text → `data_sources.code` (restrict) |  | FK |  |  |
| `external_id` | text |  |  |  |  |
| `recall_number` | text | yes |  |  |  |
| `title` | text |  |  |  |  |
| `description` | text | yes |  |  |  |
| `hazard` | text | yes |  |  |  |
| `remedy` | text | yes |  |  |  |
| `classification` | text | yes |  |  | FDA class I/II/III |
| `units_affected` | text | yes |  |  |  |
| `recall_date` | date | yes |  |  |  |
| `status` | recall_status |  |  | `'active'` |  |
| `url` | text | yes |  |  |  |
| `source_record_id` | uuid → `source_records.id` (restrict) | yes | FK |  | latest synced version |
| `search_tsv` | tsvector | yes |  |  |  |
| `synced_at` | timestamptz |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (data_source_code, external_id)`  
**Indexes:** `gin (search_tsv)`; `(recall_date DESC)`

#### `recall_regions` — ★ core · phase 1

Where a recall applies. No rows = applies everywhere its source covers.  
*Serves:* TC-P1-010 (geographic applicability)

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `recall_id` | uuid → `recalls.id` (cascade) |  | PK FK |  |  |
| `country_code` | char(2) |  | PK |  |  |
| `subdivision_code` | text |  | PK | `''` | '' = whole country |

**Primary key:** `(recall_id, country_code, subdivision_code)`  
**Indexes:** `(country_code, subdivision_code)`

#### `recall_products` — ★ core · phase 1

Each product described inside a recall notice.  
*Serves:* FR-07

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `recall_id` | uuid → `recalls.id` (cascade) |  | FK |  |  |
| `product_name` | text |  |  |  |  |
| `brand_name` | text | yes |  |  |  |
| `manufacturer_name` | text | yes |  |  |  |
| `description` | text | yes |  |  |  |
| `sold_from` | date | yes |  |  |  |
| `sold_to` | date | yes |  |  |  |
| `image_urls` | text[] |  |  | `'{}'` |  |

**Checks:** `sold_to IS NULL OR sold_from IS NULL OR sold_from <= sold_to`  
**Indexes:** `gin (brand_name gin_trgm_ops)`; `gist (product_name gist_trgm_ops(siglen=64))`

#### `recall_product_identifiers` — ★ core · phase 1

Exact identifiers listed in recalls for deterministic matching before AI.  
*Serves:* FR-07

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `recall_product_id` | uuid → `recall_products.id` (cascade) |  | FK |  |  |
| `identifier_type` | recall_identifier_type |  |  |  |  |
| `value` | text |  |  |  |  |
| `value_normalized` | text |  |  |  |  |

**Unique:** `UNIQUE (recall_product_id, identifier_type, value_normalized)`  
**Indexes:** `(identifier_type, value_normalized)`

#### `recall_embeddings` — phase 2

Semantic vectors of recall text per model (hybrid BM25 + kNN retrieval).  
*Serves:* FR-07, RCL-02

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `recall_id` | uuid → `recalls.id` (cascade) |  | PK FK |  |  |
| `model_code` | text → `embedding_models.code` (restrict) |  | PK FK |  |  |
| `content_sha256` | bytea |  |  |  | re-embed only when text changes |
| `embedding` | vector |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(recall_id, model_code)`


### Certifications

#### `certification_schemes` — ★ core · phase 1

Certification schemes (fcc, energy_star, ul, etl) and their authority source.  
*Serves:* FR-09, TC-P1-009

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `name` | text |  |  |  |  |
| `data_source_code` | text → `data_sources.code` (restrict) | yes | FK |  |  |
| `is_checkable` | boolean |  |  | `false` | false ⇒ always 'not_checked' |

#### `product_certifications` — ★ core · phase 1

A certificate claimed/found for a product. current_status caches the latest check (composite FK guarantees it is this certificate's check).  
*Serves:* FR-09, TC-P1-009

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (cascade) |  | FK |  |  |
| `scheme_code` | text → `certification_schemes.code` (restrict) |  | FK |  |  |
| `certificate_identifier` | text |  |  | `''` | FCC ID, ES ID, UL file no. |
| `holder_name` | text | yes |  |  |  |
| `current_status` | cert_status |  |  | `'pending'` |  |
| `valid_from` | date | yes |  |  |  |
| `valid_until` | date | yes |  |  |  |
| `last_check_id` | uuid → `certification_checks.id` (restrict) | yes | FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (product_id, scheme_code, certificate_identifier)`  
**Composite FKs:** `(last_check_id, id) → certification_checks(id, product_certification_id)` deferrable  
**Checks:** `valid_until IS NULL OR valid_from IS NULL OR valid_from <= valid_until`

#### `certification_checks` — ★ core · append-only · phase 1

Every lookup/manual review of a certificate — the status history.  
*Serves:* TC-P1-009 (history)

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_certification_id` | uuid → `product_certifications.id` (cascade) |  | FK |  |  |
| `status` | cert_status |  |  |  |  |
| `method` | check_method |  |  |  |  |
| `source_record_id` | uuid → `source_records.id` (restrict) | yes | FK |  |  |
| `reviewed_by_user_id` | uuid → `users.id` (restrict) | yes | FK |  |  |
| `notes` | text | yes |  |  |  |
| `checked_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (id, product_certification_id)`  
**Append-only:** insert-only  
**Checks:** `method <> 'manual_review' OR reviewed_by_user_id IS NOT NULL`; `status <> 'pending'`  
**Indexes:** `(product_certification_id, checked_at DESC)`


### Screening, Hazard & Passport

#### `screenings` — ★ core · append-only · phase 1

One recall-screening run for a product, as of a corpus snapshot. Only the completion fields may change, once.  
*Serves:* FR-08/13, PAS-03

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `run_type` | screening_run_type |  |  |  |  |
| `status` | run_status |  |  | `'running'` |  |
| `verdict` | recall_verdict | yes |  |  |  |
| `rationale` | text | yes |  |  |  |
| `candidates_considered` | smallint | yes |  |  |  |
| `corpus_synced_at` | timestamptz |  |  |  | 'no match' is only true as of this time |
| `model_code` | text | yes |  |  |  |
| `prompt_version` | text | yes |  |  |  |
| `started_at` | timestamptz |  |  | `now()` |  |
| `completed_at` | timestamptz | yes |  |  |  |

**Unique:** `UNIQUE (id, product_id)`  
**Append-only:** only `status, verdict, rationale, candidates_considered, completed_at` may change  
**Rules (triggers/functions):** Status only running→completed|failed (trigger). Deferred: verdict match/near_match ⇒ ≥1 screening_matches row with that verdict. Re-screens persist only when verdict or candidate set changes (app) — bounds growth.  
**Checks:** `(status = 'completed') = (verdict IS NOT NULL)`; `(status = 'running') = (completed_at IS NULL)`  
**Indexes:** `(product_id, started_at DESC)`

#### `screening_matches` — ★ core · append-only · phase 1

Candidate recalls retrieved for a screening and the model's per-candidate verdict.  
*Serves:* FR-07/08

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `screening_id` | uuid → `screenings.id` (cascade) |  | PK FK |  |  |
| `recall_id` | uuid → `recalls.id` (restrict) |  | PK FK |  |  |
| `rank` | smallint |  |  |  |  |
| `retrieval_score` | real | yes |  |  |  |
| `verdict` | candidate_verdict |  |  |  |  |
| `confidence` | numeric(4,3) | yes |  |  |  |
| `rationale` | text | yes |  |  |  |

**Primary key:** `(screening_id, recall_id)`  
**Append-only:** insert-only  
**Indexes:** `(recall_id)`

#### `scoring_contexts` — phase 2

Scoring frameworks (safety now; sustainability/circularity later) and their alert threshold.  
*Serves:* TC-P1-011

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `name` | text |  |  |  |  |
| `alert_threshold` | numeric(5,2) |  |  |  |  |
| `is_active` | boolean |  |  | `true` |  |

**Checks:** `alert_threshold BETWEEN 0 AND 100`

#### `scoring_bands` — phase 2

Score → label → action bands per context; ranges may not overlap.  
*Serves:* Arch v2 §9.3

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `context_code` | text → `scoring_contexts.code` (restrict) |  | PK FK |  |  |
| `label` | text |  | PK |  |  |
| `score_range` | numrange |  |  |  | e.g. [0,30) |
| `action` | text |  |  |  | approve | manual_review | block |

**Primary key:** `(context_code, label)`  
**Rules (triggers/functions):** EXCLUDE USING gist (context_code WITH =, score_range WITH &&) (needs btree_gist).  
**Checks:** `NOT isempty(score_range)`; `score_range <@ numrange(0, 100, '[]')`

#### `hazard_dimensions` — phase 2

Configurable scoring dimensions and weights. Codes are namespaced by context (safety.regulatory…).  
*Serves:* TC-P1-011

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `context_code` | text → `scoring_contexts.code` (restrict) |  | FK |  |  |
| `name` | text |  |  |  |  |
| `description` | text | yes |  |  |  |
| `weight` | numeric(4,2) |  |  |  |  |
| `sort_order` | smallint |  |  | `0` |  |
| `is_active` | boolean |  |  | `true` |  |

**Unique:** `UNIQUE (code, context_code)`  
**Checks:** `weight > 0`; `code LIKE context_code || '.%'`

#### `hazard_assessments` — append-only · phase 2

One multimodal hazard scoring run (weighted total, label, model).  
*Serves:* TC-P1-011/012

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `context_code` | text → `scoring_contexts.code` (restrict) |  | FK |  |  |
| `total_score` | numeric(5,2) | yes |  |  |  |
| `label` | text | yes |  |  |  |
| `input_modalities` | text[] |  |  |  |  |
| `has_insufficient_data` | boolean |  |  | `false` |  |
| `model_code` | text |  |  |  |  |
| `prompt_version` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (id, product_id)`; `UNIQUE (id, context_code)`  
**Append-only:** insert-only  
**Checks:** `total_score BETWEEN 0 AND 100`; `input_modalities <@ ARRAY['text','image','video']::text[] AND cardinality(input_modalities) > 0`  
**Indexes:** `(product_id, context_code, created_at DESC)`; `(context_code, total_score DESC)`

#### `hazard_dimension_scores` — append-only · phase 2

Per-dimension score + justification. Scored ⇒ ≥1 citation (deferred trigger); uncited ⇒ insufficient_data with NULL score.  
*Serves:* TC-P1-011 (hallucination guard)

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `assessment_id` | uuid → `hazard_assessments.id` (cascade) |  | PK FK |  |  |
| `context_code` | text |  |  |  | must equal the assessment's and the dimension's context |
| `dimension_code` | text → `hazard_dimensions.code` (restrict) |  | PK FK |  |  |
| `status` | dimension_score_status |  |  |  |  |
| `score` | numeric(5,2) | yes |  |  |  |
| `weight_applied` | numeric(4,2) |  |  |  |  |
| `justification` | text | yes |  |  |  |

**Primary key:** `(assessment_id, dimension_code)`  
**Composite FKs:** `(assessment_id, context_code) → hazard_assessments(id, context_code)`; `(dimension_code, context_code) → hazard_dimensions(code, context_code)`  
**Append-only:** insert-only  
**Rules (triggers/functions):** Deferred: status = 'scored' ⇒ ≥1 hazard_score_citations row.  
**Checks:** `(status = 'scored') = (score IS NOT NULL)`; `score BETWEEN 0 AND 100`; `weight_applied > 0`

#### `hazard_score_citations` — append-only · phase 2

Evidence cited for each dimension score.  
*Serves:* TC-P1-011

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `assessment_id` | uuid → `hazard_assessments.id` (cascade) |  | PK FK |  |  |
| `dimension_code` | text |  | PK |  |  |
| `evidence_id` | uuid → `evidence_items.id` (restrict) |  | PK FK |  |  |

**Primary key:** `(assessment_id, dimension_code, evidence_id)`  
**Composite FKs:** `(assessment_id, dimension_code) → hazard_dimension_scores(assessment_id, dimension_code)`  
**Append-only:** insert-only

#### `passports` — ★ core · append-only · phase 1

Versioned Product Passport. A new version on every verdict change. Composite FKs guarantee it cites THIS product's screening/assessment.  
*Serves:* FR-10/11, PAS-01

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `version` | integer |  |  |  |  |
| `tier` | smallint |  |  |  | 0 unidentified · 1 identified · 2 verified |
| `status_badge` | passport_badge |  |  |  |  |
| `trust_score` | numeric(5,2) | yes |  |  |  |
| `recall_component` | numeric(5,2) | yes |  |  |  |
| `certification_component` | numeric(5,2) | yes |  |  |  |
| `hazard_component` | numeric(5,2) | yes |  |  |  |
| `screening_id` | uuid → `screenings.id` (restrict) | yes | FK |  |  |
| `hazard_assessment_id` | uuid → `hazard_assessments.id` (restrict) | yes | FK |  |  |
| `formula_version` | text |  |  |  |  |
| `verified_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (product_id, version)`; `UNIQUE (id, product_id)`  
**Composite FKs:** `(screening_id, product_id) → screenings(id, product_id)`; `(hazard_assessment_id, product_id) → hazard_assessments(id, product_id)`  
**Append-only:** insert-only  
**Rules (triggers/functions):** Trigger: screening must be completed; verdict match ⇒ badge recalled; badge recalled ⇒ verdict match|near_match. Trigger: version = previous max + 1.  
**Checks:** `version > 0`; `tier BETWEEN 0 AND 2`; `trust_score BETWEEN 0 AND 100`; `tier = 2 OR status_badge = 'needs_information'`; `tier < 2 OR (screening_id IS NOT NULL AND trust_score IS NOT NULL)`  
**Indexes:** `(status_badge)`

#### `passport_evidence` — ★ core · append-only · phase 1

Evidence shown on a passport version, grouped by purpose.  
*Serves:* FR-11 (cited evidence)

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `passport_id` | uuid → `passports.id` (cascade) |  | PK FK |  |  |
| `evidence_id` | uuid → `evidence_items.id` (restrict) |  | PK FK |  |  |
| `purpose` | evidence_purpose |  |  |  |  |

**Primary key:** `(passport_id, evidence_id)`  
**Append-only:** insert-only


### Digital Wallet

#### `wallet_items` — ★ core · phase 1

A product in a user's Digital Wallet. Manual/barcode adds stay pending until a matching video verification exists.  
*Serves:* TC-P1-013/014, FR-12

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `add_method` | wallet_add_method |  |  |  |  |
| `identification_request_id` | uuid → `identification_requests.id` (restrict) | yes | FK |  |  |
| `status` | wallet_item_status |  |  |  | no default: app chooses by add_method |
| `verified_by_verification_id` | uuid → `wallet_item_verifications.id` (restrict) | yes | FK |  |  |
| `nickname` | text | yes |  |  |  |
| `notes` | text | yes |  |  |  |
| `alerts_enabled` | boolean |  |  | `true` |  |
| `last_seen_passport_id` | uuid → `passports.id` (restrict) | yes | FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |
| `deleted_at` | timestamptz | yes |  |  | soft delete |

**Unique:** `UNIQUE (user_id, product_id) WHERE deleted_at IS NULL`  
**Composite FKs:** `(verified_by_verification_id, id) → wallet_item_verifications(id, wallet_item_id)` deferrable; `(last_seen_passport_id, product_id) → passports(id, product_id)`  
**Rules (triggers/functions):** Verification referenced must have result = 'matched' (trigger). Active items per user ≤ app_settings wallet.max_items (app).  
**Checks:** `add_method NOT IN ('manual','barcode') OR status <> 'active' OR verified_by_verification_id IS NOT NULL`  
**Indexes:** `(user_id, created_at DESC) WHERE deleted_at IS NULL`; `(product_id) WHERE deleted_at IS NULL AND alerts_enabled`

#### `wallet_item_verifications` — ★ core · phase 1

Short-video proof that the user has the manual/barcode-added product.  
*Serves:* TC-P1-014

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `wallet_item_id` | uuid → `wallet_items.id` (cascade) |  | FK |  |  |
| `media_asset_id` | uuid → `media_assets.id` (restrict) |  | FK |  |  |
| `result` | video_check_result |  |  | `'pending'` |  |
| `confidence` | numeric(4,3) | yes |  |  |  |
| `mismatch_reason` | text | yes |  |  |  |
| `model_code` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (id, wallet_item_id)`  
**Checks:** `result <> 'mismatch' OR mismatch_reason IS NOT NULL`

#### `wallet_labels` — ★ core · phase 1

User-defined custom labels ('kitchen', 'kids room').  
*Serves:* TC-P1-013

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `name` | text |  |  |  |  |
| `color` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (user_id, lower(name))`  
**Checks:** `length(name) BETWEEN 1 AND 40`

#### `wallet_item_labels` — ★ core · phase 1

Many-to-many: wallet items ↔ labels (same owner enforced by trigger).  
*Serves:* TC-P1-013

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `wallet_item_id` | uuid → `wallet_items.id` (cascade) |  | PK FK |  |  |
| `label_id` | uuid → `wallet_labels.id` (cascade) |  | PK FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(wallet_item_id, label_id)`

#### `qr_labels` — phase 3

QR label generated for a wallet item via iotsecurityprivacy.org template.  
*Serves:* TC-P1-015

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `wallet_item_id` | uuid → `wallet_items.id` (cascade) |  | FK |  |  |
| `provider` | text |  |  | `'iotsecurityprivacy'` |  |
| `template_code` | text |  |  |  |  |
| `status` | qr_label_status |  |  | `'pending'` |  |
| `external_label_id` | text | yes |  |  |  |
| `payload_url` | text | yes |  |  |  |
| `image_media_id` | uuid → `media_assets.id` (restrict) | yes | FK |  |  |
| `error` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `status <> 'generated' OR payload_url IS NOT NULL`; `status <> 'failed' OR error IS NOT NULL`  
**Indexes:** `(wallet_item_id, created_at DESC)`

#### `product_watches` — phase 3

Watch a product not in the wallet (granted by a watchlist entitlement).  
*Serves:* TC-P1-017d

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `entitlement_id` | uuid → `user_entitlements.id` (restrict) |  | FK |  |  |
| `expires_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (user_id, product_id)`


### Rewards (TelCoins)

#### `coin_earn_rules` — phase 3

Configurable earning rules (amount, limits, confirmation window).  
*Serves:* TC-P1-016

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `amount` | bigint |  |  |  |  |
| `counts_toward_daily_cap` | boolean |  |  | `true` |  |
| `per_subject_limit` | integer | yes |  |  | e.g. review: 5 per product |
| `lifetime_limit` | integer | yes |  |  | one-time bonuses = 1 |
| `confirmation_delay` | interval |  |  | `'10 minutes'` |  |
| `is_active` | boolean |  |  | `true` |  |

**Checks:** `amount > 0`; `per_subject_limit IS NULL OR per_subject_limit > 0`; `lifetime_limit IS NULL OR lifetime_limit > 0`

#### `coin_ledger_entries` — append-only · phase 3

Append-only TelCoin ledger. Only status moves (pending→confirmed|frozen|reversed, frozen→confirmed|reversed). Writes go through coin_* functions.  
*Serves:* TC-P1-016/017, Arch v2 §6

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `entry_type` | ledger_entry_type |  |  |  |  |
| `amount` | bigint |  |  |  | + earn/bonus/refund · − spend/clawback · ± adjustment |
| `status` | ledger_status |  |  |  |  |
| `rule_code` | text → `coin_earn_rules.code` (restrict) | yes | FK |  |  |
| `subject_type` | text | yes |  |  | product | review | media_asset | hazard_flag | referral | redemption |
| `subject_id` | uuid | yes |  |  | per-subject limit key (e.g. product for reviews) |
| `reference_type` | text | yes |  |  |  |
| `reference_id` | uuid | yes |  |  |  |
| `reverses_entry_id` | uuid → `coin_ledger_entries.id` (restrict) | yes | FK |  |  |
| `fraud_hold_id` | uuid → `fraud_holds.id` (restrict) | yes | FK |  |  |
| `idempotency_key` | text |  | UK |  |  |
| `confirmable_at` | timestamptz | yes |  |  |  |
| `status_changed_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (reverses_entry_id) WHERE entry_type IN ('clawback','refund')`  
**Append-only:** only `status, status_changed_at, fraud_hold_id, confirmable_at` may change  
**Rules (triggers/functions):** Status transitions validated by trigger. coin_earn(): locks coin_balances row, enforces daily cap (app_settings rewards.daily_cap), limits, idempotency. coin_spend(): locks balance row, requires confirmed_balance ≥ cost. coin_clawback(): may drive confirmed_balance negative (debt repaid by future earnings).  
**Checks:** `amount <> 0`; `entry_type NOT IN ('earn','level_bonus','refund') OR amount > 0`; `entry_type NOT IN ('spend','clawback') OR amount < 0`; `entry_type NOT IN ('spend','clawback','refund','adjustment') OR status = 'confirmed'`; `entry_type NOT IN ('clawback','refund') OR reverses_entry_id IS NOT NULL`; `entry_type NOT IN ('earn') OR rule_code IS NOT NULL`; `status <> 'pending' OR confirmable_at IS NOT NULL`  
**Indexes:** `(user_id, created_at DESC)`; `(user_id, rule_code, subject_id) WHERE entry_type = 'earn'`; `(confirmable_at) WHERE status = 'pending'`

#### `coin_balances` — phase 3

Per-user balances maintained by coin_* functions in the same transaction; row lock serialises earn/spend. Rebuildable from the ledger.  
*Serves:* TC-P1-016/018

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `user_id` | uuid → `users.id` (cascade) |  | PK FK |  |  |
| `confirmed_balance` | bigint |  |  | `0` | may be negative after clawback (debt) |
| `pending_balance` | bigint |  |  | `0` |  |
| `frozen_balance` | bigint |  |  | `0` |  |
| `lifetime_earned` | bigint |  |  | `0` | drives reward level |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(user_id)`  
**Checks:** `pending_balance >= 0`; `frozen_balance >= 0`; `lifetime_earned >= 0`

#### `reward_levels` — phase 3

Level ladder (Novice → Master) by LIFETIME coins earned; a user's level is derived, never stored.  
*Serves:* TC-P1-018

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `level` | smallint |  | PK |  |  |
| `title` | text |  | UK |  |  |
| `min_lifetime_coins` | bigint |  | UK |  |  |
| `earn_bonus_pct` | numeric(4,1) |  |  | `0` |  |
| `perks` | jsonb |  |  | `'[]'` |  |

**Checks:** `level > 0`; `min_lifetime_coins >= 0`; `earn_bonus_pct BETWEEN 0 AND 100`

#### `redemption_items` — phase 3

Catalogue of what coins buy.  
*Serves:* TC-P1-017

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `name` | text |  |  |  |  |
| `cost_coins` | bigint |  |  |  |  |
| `fulfilment_type` | fulfilment_type |  |  |  |  |
| `duration` | interval | yes |  |  |  |
| `quantity` | integer | yes |  |  |  |
| `is_active` | boolean |  |  | `true` |  |

**Rules (triggers/functions):** Phase one sells only pdf_report and watchlist_slots items; the rest are is_active = false (D13, WO-019). coin_redeem() refuses an inactive item.  
**Checks:** `cost_coins > 0`; `quantity IS NULL OR quantity > 0`

#### `redemptions` — phase 3

A redemption; its spend is exactly one ledger entry. Fulfilment evidence recorded.  
*Serves:* TC-P1-017

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `item_code` | text → `redemption_items.code` (restrict) |  | FK |  |  |
| `ledger_entry_id` | uuid → `coin_ledger_entries.id` (restrict) |  | FK UK |  |  |
| `product_id` | uuid → `products.id` (restrict) | yes | FK |  |  |
| `status` | redemption_status |  |  | `'processing'` |  |
| `fulfilment` | jsonb | yes |  |  |  |
| `fulfilled_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Rules (triggers/functions):** coin_redeem(): spend + redemption in one transaction, idempotent on its key. coin_refund_redemption(): a processing or failed redemption with nothing delivered gets one confirmed refund entry reversing its spend and becomes refunded; a repeat returns the same entry and pays nothing. No redemption is left processing (WO-019): one that cannot be fulfilled is refunded.  
**Checks:** `(status = 'fulfilled') = (fulfilled_at IS NOT NULL)`  
**Indexes:** `(user_id, created_at DESC)`

#### `user_entitlements` — phase 3

Time-boxed rights from redemptions, level perks or admins (rate boost, feature access, watchlist slots).  
*Serves:* TC-P1-017/018

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `source` | entitlement_source |  |  |  |  |
| `redemption_id` | uuid → `redemptions.id` (restrict) | yes | FK |  |  |
| `entitlement` | text |  |  |  | rate_limit_x3 | feature:<flag> | watchlist_slots |
| `quantity` | integer | yes |  |  |  |
| `starts_at` | timestamptz |  |  | `now()` |  |
| `ends_at` | timestamptz | yes |  |  |  |

**Checks:** `(source = 'redemption') = (redemption_id IS NOT NULL)`; `ends_at IS NULL OR ends_at > starts_at`  
**Indexes:** `(user_id, entitlement, ends_at)`

#### `fraud_holds` — phase 3

Automatic or manual freeze of a user's earning pending review.  
*Serves:* TC-P1-016

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `reason` | text |  |  |  |  |
| `rule_triggered` | text | yes |  |  |  |
| `status` | hold_status |  |  | `'open'` |  |
| `resolved_by_user_id` | uuid → `users.id` (restrict) | yes | FK |  |  |
| `resolved_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `(status = 'open') = (resolved_at IS NULL)`  
**Indexes:** `(user_id) WHERE status = 'open'`

#### `referrals` — phase 3

Referrer ↔ referred user; rewarded once the friend reaches Level 1. The single source of 'who referred whom'.  
*Serves:* TC-P1-016g/026

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `referrer_user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `referred_user_id` | uuid → `users.id` (restrict) |  | FK UK |  |  |
| `status` | referral_status |  |  | `'pending'` |  |
| `qualified_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `referrer_user_id <> referred_user_id`

#### `user_daily_logins` — phase 3

One row per user per active day (user's time zone); streak length derived.  
*Serves:* TC-P1-016f

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `user_id` | uuid → `users.id` (cascade) |  | PK FK |  |  |
| `login_date` | date |  | PK |  |  |

**Primary key:** `(user_id, login_date)`

#### `badges` — phase 3

Badge catalogue (Inspector…Master, beta tester, verified identity).  
*Serves:* TC-P1-017c/018

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `name` | text |  |  |  |  |
| `description` | text | yes |  |  |  |

#### `user_badges` — phase 3

Badges awarded to users.  
*Serves:* TC-P1-018

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `user_id` | uuid → `users.id` (cascade) |  | PK FK |  |  |
| `badge_code` | text → `badges.code` (restrict) |  | PK FK |  |  |
| `awarded_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(user_id, badge_code)`


### Community & Reviews

#### `chat_threads` — phase 2

A member's conversation with the product assistant about one product (its memory).  
*Serves:* WO-015 product assistant

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `product_id` | uuid → `products.id` (cascade) |  | FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `last_message_at` | timestamptz |  |  | `now()` |  |

**Indexes:** `(user_id, product_id, last_message_at DESC)`

#### `chat_messages` — append-only · phase 2

One turn of a conversation. An answer keeps the evidence it cited and the model that wrote it.  
*Serves:* WO-015 product assistant

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `thread_id` | uuid → `chat_threads.id` (cascade) |  | FK |  |  |
| `role` | text |  |  |  |  |
| `content` | text |  |  |  |  |
| `citations` | jsonb |  |  | `'[]'::jsonb` | [{evidence_id, url, excerpt}] |
| `model_code` | text | yes |  |  |  |
| `prompt_version` | text | yes |  |  |  |
| `input_tokens` | integer | yes |  |  |  |
| `output_tokens` | integer | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Append-only:** insert-only  
**Checks:** `role IN ('user', 'assistant')`; `char_length(content) BETWEEN 1 AND 8000`  
**Indexes:** `(thread_id, created_at)`

#### `reviews` — ★ core · phase 1

Product reviews by users, or ingested from marketplaces (keyed on source + external id so re-ingestion updates, not duplicates).  
*Serves:* TC-P1-022

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `origin` | content_origin |  |  | `'user'` |  |
| `author_user_id` | uuid → `users.id` (restrict) | yes | FK |  |  |
| `data_source_code` | text → `data_sources.code` (restrict) | yes | FK |  |  |
| `external_id` | text | yes |  |  |  |
| `source_record_id` | uuid → `source_records.id` (restrict) | yes | FK |  | latest version |
| `rating` | smallint |  |  |  |  |
| `title` | text | yes |  |  |  |
| `body` | text |  |  |  |  |
| `author_reward_level` | smallint | yes |  |  | snapshot at writing time |
| `verified_owner` | boolean |  |  | `false` |  |
| `geohash` | text | yes |  |  | ~1 km cell, optional |
| `helpful_count` | integer |  |  | `0` |  |
| `status` | content_status |  |  | `'published'` |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |
| `deleted_at` | timestamptz | yes |  |  | soft delete |

**Unique:** `UNIQUE (data_source_code, external_id) WHERE origin = 'ingested'`  
**Checks:** `rating BETWEEN 1 AND 5`; `(origin = 'user') = (author_user_id IS NOT NULL)`; `(origin = 'ingested') = (data_source_code IS NOT NULL AND external_id IS NOT NULL AND source_record_id IS NOT NULL)`; `helpful_count >= 0`; `geohash IS NULL OR geohash ~ '^[0-9b-hjkmnp-z]{6}$'`  
**Indexes:** `(product_id, created_at DESC) WHERE deleted_at IS NULL`; `(author_user_id, created_at DESC)`; `(geohash text_pattern_ops) WHERE geohash IS NOT NULL`

#### `review_media` — ★ core · phase 1

Photos attached to a review.  
*Serves:* TC-P1-022

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `review_id` | uuid → `reviews.id` (cascade) |  | PK FK |  |  |
| `media_asset_id` | uuid → `media_assets.id` (restrict) |  | PK FK |  |  |
| `sort_order` | smallint |  |  | `0` |  |

**Primary key:** `(review_id, media_asset_id)`

#### `review_votes` — ★ core · phase 1

'Helpful' votes — one per user per review.  
*Serves:* TC-P1-022

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `review_id` | uuid → `reviews.id` (cascade) |  | PK FK |  |  |
| `user_id` | uuid → `users.id` (cascade) |  | PK FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(review_id, user_id)`

#### `posts` — phase 3

Community post about a product. Location stored only as a ~1 km geohash cell (privacy).  
*Serves:* TC-P1-021/025

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `author_user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `wallet_item_id` | uuid → `wallet_items.id` (set null) | yes | FK |  |  |
| `body` | text |  |  |  |  |
| `geohash` | text | yes |  |  | precision 6 ≈ 1.2 km |
| `location_name` | text | yes |  |  |  |
| `country_code` | char(2) | yes |  |  |  |
| `status` | content_status |  |  | `'published'` |  |
| `comment_count` | integer |  |  | `0` |  |
| `reaction_count` | integer |  |  | `0` |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |
| `deleted_at` | timestamptz | yes |  |  | soft delete |

**Checks:** `geohash IS NULL OR geohash ~ '^[0-9b-hjkmnp-z]{6}$'`; `comment_count >= 0`; `reaction_count >= 0`  
**Indexes:** `(geohash text_pattern_ops) WHERE geohash IS NOT NULL`; `(product_id, created_at DESC)`; `(created_at DESC) WHERE status = 'published' AND deleted_at IS NULL`

#### `post_media` — phase 3

Photos/videos attached to a post.  
*Serves:* TC-P1-021

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `post_id` | uuid → `posts.id` (cascade) |  | PK FK |  |  |
| `media_asset_id` | uuid → `media_assets.id` (restrict) |  | PK FK |  |  |
| `sort_order` | smallint |  |  | `0` |  |

**Primary key:** `(post_id, media_asset_id)`

#### `comments` — phase 3

Threaded discussion on a post or on a risk event (Risk Timeline community thread).  
*Serves:* TC-P1-025/029

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `post_id` | uuid → `posts.id` (cascade) | yes | FK |  |  |
| `risk_event_id` | uuid → `risk_events.id` (cascade) | yes | FK |  |  |
| `author_user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `parent_comment_id` | uuid → `comments.id` (cascade) | yes | FK |  |  |
| `body` | text |  |  |  |  |
| `status` | content_status |  |  | `'published'` |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |
| `deleted_at` | timestamptz | yes |  |  | soft delete |

**Checks:** `num_nonnulls(post_id, risk_event_id) = 1`; `parent_comment_id IS NULL OR parent_comment_id <> id`  
**Indexes:** `(post_id, created_at)`; `(risk_event_id, created_at)`

#### `reactions` — phase 3

One reaction per user per post.  
*Serves:* TC-P1-025

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `post_id` | uuid → `posts.id` (cascade) |  | PK FK |  |  |
| `user_id` | uuid → `users.id` (cascade) |  | PK FK |  |  |
| `reaction` | reaction_type |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Primary key:** `(post_id, user_id)`

#### `hazard_flags` — phase 3

User-reported suspected hazard; coins only once confirmed (recall match or moderator).  
*Serves:* TC-P1-023

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `reporter_user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `wallet_item_id` | uuid → `wallet_items.id` (set null) | yes | FK |  |  |
| `dimension_code` | text → `hazard_dimensions.code` (restrict) | yes | FK |  | hazard type |
| `description` | text | yes |  |  |  |
| `geohash` | text | yes |  |  |  |
| `status` | flag_status |  |  | `'pending'` |  |
| `matched_recall_id` | uuid → `recalls.id` (restrict) | yes | FK |  |  |
| `reviewed_by_user_id` | uuid → `users.id` (restrict) | yes | FK |  |  |
| `reviewed_at` | timestamptz | yes |  |  |  |
| `resolution_note` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `geohash IS NULL OR geohash ~ '^[0-9b-hjkmnp-z]{6}$'`; `(status = 'pending') = (reviewed_at IS NULL)`; `status <> 'confirmed' OR matched_recall_id IS NOT NULL OR reviewed_by_user_id IS NOT NULL`  
**Indexes:** `(product_id, status)`; `(reporter_user_id, created_at DESC)`

#### `hazard_flag_media` — phase 3

Evidence photos on a hazard flag.  
*Serves:* TC-P1-023

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `hazard_flag_id` | uuid → `hazard_flags.id` (cascade) |  | PK FK |  |  |
| `media_asset_id` | uuid → `media_assets.id` (restrict) |  | PK FK |  |  |

**Primary key:** `(hazard_flag_id, media_asset_id)`

#### `product_fact_reports` — phase 3

User confirms or corrects a flagged product fact; accepted reports earn coins.  
*Serves:* TC-P1-016h

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `reporter_user_id` | uuid → `users.id` (restrict) |  | FK |  |  |
| `hazard_flag_id` | uuid → `hazard_flags.id` (restrict) | yes | FK |  | flag being verified, if any |
| `attribute` | text |  |  |  |  |
| `current_value` | text | yes |  |  |  |
| `proposed_value` | text | yes |  |  |  |
| `is_confirmation` | boolean |  |  |  |  |
| `status` | fact_report_status |  |  | `'pending'` |  |
| `reviewed_by_user_id` | uuid → `users.id` (restrict) | yes | FK |  |  |
| `reviewed_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `is_confirmation OR proposed_value IS NOT NULL`; `(status = 'pending') = (reviewed_at IS NULL)`


### Commerce Feed & Personalisation

#### `topics` — phase 3

Attribute/topic filter values.  
*Serves:* TC-P1-007

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `name` | text |  |  |  |  |
| `sort_order` | smallint |  |  | `0` |  |

#### `feed_items` — phase 3

A card in For You / Explore, keyed on its origin so re-ingestion updates rather than duplicates.  
*Serves:* TC-P1-004/007

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `item_type` | feed_item_type |  |  |  |  |
| `data_source_code` | text → `data_sources.code` (restrict) |  | FK |  |  |
| `external_id` | text | yes |  |  |  |
| `source_record_id` | uuid → `source_records.id` (restrict) | yes | FK |  |  |
| `media_asset_id` | uuid → `media_assets.id` (restrict) | yes | FK |  |  |
| `post_id` | uuid → `posts.id` (cascade) | yes | FK |  |  |
| `recall_id` | uuid → `recalls.id` (restrict) | yes | FK |  |  |
| `product_id` | uuid → `products.id` (restrict) | yes | FK |  |  |
| `category_id` | uuid → `categories.id` (restrict) | yes | FK |  |  |
| `country_code` | char(2) | yes |  |  |  |
| `title` | text | yes |  |  |  |
| `ai_label` | text | yes |  |  |  |
| `ai_confidence` | numeric(4,3) | yes |  |  |  |
| `trending_score` | real |  |  | `0` | not indexed (keeps HOT updates) |
| `is_public` | boolean |  |  | `true` |  |
| `published_at` | timestamptz |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (data_source_code, external_id) WHERE external_id IS NOT NULL`; `UNIQUE (post_id) WHERE post_id IS NOT NULL`; `UNIQUE (recall_id) WHERE item_type = 'recall'`; `UNIQUE (media_asset_id) WHERE item_type = 'user_upload'`  
**Checks:** `item_type <> 'user_upload' OR media_asset_id IS NOT NULL`; `item_type NOT IN ('listing','social_post') OR (external_id IS NOT NULL AND source_record_id IS NOT NULL)`; `item_type <> 'recall' OR recall_id IS NOT NULL`; `item_type <> 'community_post' OR post_id IS NOT NULL`; `ai_confidence BETWEEN 0 AND 1`  
**Indexes:** `(published_at DESC) WHERE is_public`; `(country_code, category_id, published_at DESC)`; `(data_source_code, published_at DESC)`

#### `feed_item_topics` — phase 3

Topics tagged on a feed item (AI-assigned with confidence).  
*Serves:* TC-P1-007

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `feed_item_id` | uuid → `feed_items.id` (cascade) |  | PK FK |  |  |
| `topic_code` | text → `topics.code` (restrict) |  | PK FK |  |  |
| `confidence` | numeric(4,3) | yes |  |  |  |

**Primary key:** `(feed_item_id, topic_code)`  
**Indexes:** `(topic_code, feed_item_id)`

#### `search_queries` — append-only · phase 3

User search history (text or image).  
*Serves:* TC-P1-007/013

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `query_text` | text | yes |  |  |  |
| `query_media_id` | uuid → `media_assets.id` (set null) | yes | FK |  |  |
| `clicked_product_id` | uuid → `products.id` (restrict) | yes | FK |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Append-only:** insert-only  
**Checks:** `num_nonnulls(query_text, query_media_id) >= 1`  
**Indexes:** `(user_id, created_at DESC)`

#### `feed_interactions` — append-only · phase 3

Implicit feedback for ranking. Monthly partitions.  
*Serves:* TC-P1-007

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid |  |  |  | no FK on partitioned log; purged on account deletion |
| `feed_item_id` | uuid |  |  |  |  |
| `action` | feed_action |  |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Partitioned:** monthly by `created_at` (PK includes it)  
**Append-only:** insert-only  
**Indexes:** `(user_id, created_at DESC)`


### Pricing

#### `price_snapshots` — append-only · phase 3

Observed prices per product, source, seller and currency over time.  
*Serves:* TC-P1-024

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `data_source_code` | text → `data_sources.code` (restrict) |  | FK |  |  |
| `seller_name` | text | yes |  |  |  |
| `listing_url` | text | yes |  |  |  |
| `country_code` | char(2) |  |  |  |  |
| `currency` | char(3) |  |  |  |  |
| `price` | numeric(12,2) |  |  |  |  |
| `in_stock` | boolean | yes |  |  |  |
| `observed_at` | timestamptz |  |  |  |  |

**Append-only:** insert-only  
**Checks:** `price >= 0`; `currency ~ '^[A-Z]{3}$'`  
**Indexes:** `(product_id, currency, observed_at DESC)`

#### `price_alerts` — phase 3

Target-price alert on a wallet product (owner = wallet item's user).  
*Serves:* TC-P1-024

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `wallet_item_id` | uuid → `wallet_items.id` (cascade) |  | FK |  |  |
| `target_price` | numeric(12,2) |  |  |  |  |
| `currency` | char(3) |  |  |  |  |
| `status` | price_alert_status |  |  | `'active'` |  |
| `last_triggered_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (wallet_item_id) WHERE status = 'active'`  
**Checks:** `target_price > 0`; `currency ~ '^[A-Z]{3}$'`


### Risk Events & Notifications

#### `risk_events` — append-only · phase 3

A product-level risk signal, created once per (product, cause) — re-screens do not duplicate it.  
*Serves:* TC-P1-029, FR-13, PAS-04

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `product_id` | uuid → `products.id` (restrict) |  | FK |  |  |
| `event_type` | risk_event_type |  |  |  |  |
| `severity` | severity |  |  |  |  |
| `screening_id` | uuid → `screenings.id` (restrict) | yes | FK |  |  |
| `recall_id` | uuid → `recalls.id` (restrict) | yes | FK |  |  |
| `certification_check_id` | uuid → `certification_checks.id` (restrict) | yes | FK |  |  |
| `hazard_assessment_id` | uuid → `hazard_assessments.id` (restrict) | yes | FK |  |  |
| `price_snapshot_id` | uuid → `price_snapshots.id` (restrict) | yes | FK |  |  |
| `hazard_flag_id` | uuid → `hazard_flags.id` (restrict) | yes | FK |  |  |
| `title` | text |  |  |  |  |
| `summary` | text | yes |  |  |  |
| `detected_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (product_id, event_type, recall_id) WHERE recall_id IS NOT NULL`; `UNIQUE (certification_check_id) WHERE certification_check_id IS NOT NULL`; `UNIQUE (hazard_assessment_id) WHERE hazard_assessment_id IS NOT NULL`; `UNIQUE (price_snapshot_id) WHERE price_snapshot_id IS NOT NULL`; `UNIQUE (hazard_flag_id) WHERE hazard_flag_id IS NOT NULL`  
**Composite FKs:** `(screening_id, product_id) → screenings(id, product_id)`; `(hazard_assessment_id, product_id) → hazard_assessments(id, product_id)`  
**Append-only:** insert-only  
**Checks:** `CASE event_type WHEN 'recall_match' THEN recall_id IS NOT NULL AND screening_id IS NOT NULL WHEN 'recall_near_match' THEN recall_id IS NOT NULL AND screening_id IS NOT NULL WHEN 'hazard_threshold' THEN hazard_assessment_id IS NOT NULL WHEN 'certification_change' THEN certification_check_id IS NOT NULL WHEN 'price_drop' THEN price_snapshot_id IS NOT NULL WHEN 'community_flag_confirmed' THEN hazard_flag_id IS NOT NULL END`  
**Indexes:** `(product_id, detected_at DESC)`

#### `risk_event_media` — phase 3

Images/videos shown in a risk instance's detail feed.  
*Serves:* TC-P1-029

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `risk_event_id` | uuid → `risk_events.id` (cascade) |  | PK FK |  |  |
| `media_asset_id` | uuid → `media_assets.id` (restrict) |  | PK FK |  |  |
| `sort_order` | smallint |  |  | `0` |  |

**Primary key:** `(risk_event_id, media_asset_id)`

#### `user_risk_alerts` — phase 3

A risk instance in one user's timeline; the user investigates then confirms or dismisses.  
*Serves:* TC-P1-029

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `risk_event_id` | uuid → `risk_events.id` (restrict) |  | FK |  |  |
| `wallet_item_id` | uuid → `wallet_items.id` (set null) | yes | FK |  |  |
| `price_alert_id` | uuid → `price_alerts.id` (set null) | yes | FK |  |  |
| `status` | risk_alert_status |  |  | `'new'` |  |
| `action_taken` | text | yes |  |  |  |
| `seen_at` | timestamptz | yes |  |  |  |
| `resolved_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (user_id, risk_event_id)`  
**Checks:** `status NOT IN ('confirmed','dismissed','resolved') OR resolved_at IS NOT NULL`  
**Indexes:** `(user_id, created_at DESC)`; `(user_id) WHERE status = 'new'`

#### `notifications` — phase 3

Outbound notification per channel with delivery status.  
*Serves:* PAS-04, TC-P1-010/024/029

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `channel` | notification_channel |  |  |  |  |
| `template_code` | text |  |  |  |  |
| `payload` | jsonb |  |  | `'{}'` |  |
| `user_risk_alert_id` | uuid → `user_risk_alerts.id` (set null) | yes | FK |  |  |
| `status` | notification_status |  |  | `'queued'` |  |
| `error` | text | yes |  |  |  |
| `sent_at` | timestamptz | yes |  |  |  |
| `read_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Indexes:** `(user_id, created_at DESC)`; `(created_at) WHERE status = 'queued'`

#### `notification_preferences` — phase 3

Per-user, per-channel, per-category opt in/out.

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `user_id` | uuid → `users.id` (cascade) |  | PK FK |  |  |
| `channel` | notification_channel |  | PK |  |  |
| `category` | text |  | PK |  | recall | price | community | marketing |
| `enabled` | boolean |  |  | `true` |  |

**Primary key:** `(user_id, channel, category)`

#### `user_devices` — phase 3

Push tokens for the (future) mobile app and web push.  
*Serves:* future mobile app

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `user_id` | uuid → `users.id` (cascade) |  | FK |  |  |
| `platform` | text |  |  |  |  |
| `push_token` | text |  | UK |  |  |
| `last_seen_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Checks:** `platform IN ('ios','android','web')`


### Platform, Audit & Operations

#### `app_settings` — ★ core · phase 1

Typed runtime settings: quotas, caps, thresholds (wallet.max_items, identify.daily_quota, rewards.daily_cap, session timeouts…).  
*Serves:* NFR-02, D9 config-as-data

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `key` | text |  | PK |  |  |
| `value` | jsonb |  |  |  |  |
| `description` | text | yes |  |  |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Checks:** `key ~ '^[a-z0-9_]+(\.[a-z0-9_]+)+$'`

#### `audit_log` — ★ core · append-only · phase 1

Permanent audit of every significant write. Monthly partitions.  
*Serves:* FR-16, NFR-03

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `actor_type` | actor_type |  |  |  |  |
| `actor_user_id` | uuid | yes |  |  | no FK — survives account anonymisation |
| `action` | text |  |  |  |  |
| `entity_type` | text |  |  |  |  |
| `entity_id` | uuid | yes |  |  |  |
| `request_id` | text | yes |  |  |  |
| `trace_id` | text | yes |  |  |  |
| `ip_address` | inet | yes |  |  |  |
| `changes` | jsonb | yes |  |  |  |
| `metadata` | jsonb | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Partitioned:** monthly by `created_at` (PK includes it)  
**Append-only:** insert-only  
**Indexes:** `(entity_type, entity_id, created_at DESC)`; `(actor_user_id, created_at DESC)`

#### `review_tasks` — phase 2

Unified human-review queue; user-submitted material (e.g. manual certification evidence) in payload.  
*Serves:* TC-P1-009/011/023

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `task_type` | review_task_type |  |  |  |  |
| `subject_type` | text |  |  |  |  |
| `subject_id` | uuid |  |  |  |  |
| `status` | review_task_status |  |  | `'open'` |  |
| `priority` | smallint |  |  | `3` |  |
| `submitted_by_user_id` | uuid → `users.id` (set null) | yes | FK |  |  |
| `payload` | jsonb |  |  | `'{}'` |  |
| `assigned_to_user_id` | uuid → `users.id` (set null) | yes | FK |  |  |
| `resolution` | text | yes |  |  |  |
| `resolved_at` | timestamptz | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |

**Unique:** `UNIQUE (task_type, subject_type, subject_id) WHERE status IN ('open','in_progress')`  
**Checks:** `priority BETWEEN 1 AND 5`; `(status IN ('resolved','dismissed')) = (resolved_at IS NOT NULL)`  
**Indexes:** `(status, priority, created_at)`

#### `ai_invocations` — append-only · phase 2

Every model call: purpose, model, tokens, cost, latency — quotas, budgets, evals. Monthly partitions.  
*Serves:* NFR-02, D-05

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `purpose` | ai_purpose |  |  |  |  |
| `model_code` | text |  |  |  |  |
| `prompt_version` | text | yes |  |  |  |
| `user_id` | uuid | yes |  |  |  |
| `subject_type` | text | yes |  |  |  |
| `subject_id` | uuid | yes |  |  |  |
| `input_tokens` | integer | yes |  |  |  |
| `output_tokens` | integer | yes |  |  |  |
| `cost_usd` | numeric(10,6) | yes |  |  |  |
| `latency_ms` | integer | yes |  |  |  |
| `succeeded` | boolean |  |  |  |  |
| `error` | text | yes |  |  |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Partitioned:** monthly by `created_at` (PK includes it)  
**Append-only:** insert-only  
**Indexes:** `(user_id, created_at DESC)`; `(purpose, model_code, created_at DESC)`

#### `outbox_events` — phase 2

Transactional outbox: events written with the change, published afterwards.  
*Serves:* event-driven alerts, re-screen fan-out

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `id` | uuid |  | PK | `uuidv7()` |  |
| `aggregate_type` | text |  |  |  |  |
| `aggregate_id` | uuid |  |  |  |  |
| `event_type` | text |  |  |  |  |
| `payload` | jsonb |  |  |  |  |
| `published_at` | timestamptz | yes |  |  |  |
| `attempts` | smallint |  |  | `0` |  |
| `created_at` | timestamptz |  |  | `now()` |  |

**Indexes:** `(created_at) WHERE published_at IS NULL`

#### `feature_flags` — phase 3

Feature flags / early-access gates.  
*Serves:* TC-P1-017c

| Column | Type | Null | Key | Default | Notes |
|---|---|---|---|---|---|
| `code` | text |  | PK |  |  |
| `description` | text | yes |  |  |  |
| `is_enabled` | boolean |  |  | `false` |  |
| `rollout` | jsonb |  |  | `'{}'` |  |
| `updated_at` | timestamptz |  |  | `now()` |  |


### Enumerated types

| Enum | Values |
|---|---|
| `user_status` | pending, active, suspended, deleted |
| `user_role` | user, moderator, admin |
| `auth_provider` | google, facebook, apple |
| `token_purpose` | email_verification, phone_otp, password_reset, email_change |
| `auth_event_type` | login_succeeded, login_failed, logout, session_refreshed, session_revoked, token_reuse_detected, password_reset_requested, password_changed, oauth_linked, oauth_unlinked, account_locked, account_unlocked, otp_sent, otp_failed, email_verified, phone_verified |
| `identity_check_status` | pending, passed, failed |
| `product_status` | active, discontinued, flagged, merged |
| `identification_source` | ai_image, ai_video, barcode, text, ingestion, manual, admin |
| `traceability_status` | pending, traced, untraceable |
| `alias_type` | gtin, marketplace_item, retailer_sku, other |
| `media_kind` | image, video |
| `media_role` | primary, gallery, label, nameplate, packaging |
| `moderation_status` | pending, approved, rejected |
| `visibility` | private, public |
| `capture_input` | image, video, barcode, text |
| `identification_status` | pending, identified, needs_input, failed |
| `data_source_kind` | recall_authority, certification_authority, marketplace, social, product_reference, user, internal |
| `job_trigger` | schedule, admin, system, event |
| `job_status` | queued, running, succeeded, partial, failed, cancelled |
| `source_record_type` | product_listing, review, social_post, recall, certification, price, other |
| `evidence_kind` | recall, certification_check, source_record, media_region, review, hazard_flag, web_document |
| `evidence_purpose` | identity, recall, certification, hazard, traceability |
| `recall_status` | active, closed |
| `recall_identifier_type` | gtin, model_number, serial_range, lot_code, sku, date_code |
| `cert_status` | pending, valid, expired, revoked, not_found, not_checked, lookup_failed |
| `check_method` | api, manual_review |
| `screening_run_type` | initial, rescreen, manual |
| `run_status` | running, completed, failed |
| `recall_verdict` | match, near_match, no_match_found, insufficient_information |
| `candidate_verdict` | match, near_match, rejected |
| `dimension_score_status` | scored, insufficient_data |
| `passport_badge` | verified, recalled, certification_issue, needs_information |
| `embedding_modality` | text, image, multimodal |
| `wallet_add_method` | media_grid, manual, barcode, search, extension |
| `wallet_item_status` | pending_verification, active, rejected |
| `video_check_result` | pending, matched, mismatch, failed |
| `qr_label_status` | pending, generated, failed |
| `ledger_entry_type` | earn, level_bonus, spend, clawback, adjustment, refund |
| `ledger_status` | pending, confirmed, frozen, reversed |
| `fulfilment_type` | pdf_report, rate_limit_boost, feature_access, watchlist_slots, data_export, invoice_discount |
| `redemption_status` | processing, fulfilled, failed, refunded |
| `entitlement_source` | redemption, level_perk, admin |
| `hold_status` | open, released, confirmed_fraud |
| `referral_status` | pending, qualified, rewarded, void |
| `content_status` | published, hidden, removed |
| `content_origin` | user, ingested |
| `flag_status` | pending, confirmed, rejected |
| `fact_report_status` | pending, accepted, rejected |
| `reaction_type` | like, helpful, concerned, same_issue |
| `feed_item_type` | user_upload, listing, social_post, recall, community_post |
| `feed_action` | impression, open, save, share, hide |
| `price_alert_status` | active, triggered, cancelled |
| `risk_event_type` | recall_match, recall_near_match, hazard_threshold, certification_change, price_drop, community_flag_confirmed |
| `severity` | info, low, medium, high, critical |
| `risk_alert_status` | new, seen, confirmed, dismissed, resolved |
| `notification_channel` | in_app, email, push, sms |
| `notification_status` | queued, sent, delivered, failed, read |
| `actor_type` | user, admin, system, job, model |
| `review_task_type` | media_moderation, hazard_insufficient_data, certification_manual_review, hazard_flag, fact_report, fraud_hold, identity_verification, content_report |
| `review_task_status` | open, in_progress, resolved, dismissed |
| `ai_purpose` | identify, identify_escalation, adjudicate, hazard_score, annotate, embed, moderate, video_verify, ocr |
<!-- CATALOGUE:END -->

## 13. Working with the schema

```bash
make db-up            # start Postgres 18 (localhost:5433, data in volume telcron_pgdata)
make db-migrate       # apply migrations (dbmate in a container)
make db-seed          # reference data          make db-sample   # fictional demo data
make db-reset         # wipe + migrate + seed + demo
make db-test          # 66 schema tests          make db-test-perf  # read-path performance
make db-gen           # after editing schema_spec.py: regenerate SQL, ERD, catalogue
```

Changing the schema: edit `schema_spec.py` (and the hand-written `*_rules.sql` if behaviour changes) →
`make db-gen` → add a **new** timestamped migration for the delta (never edit an applied migration) → add a test.
