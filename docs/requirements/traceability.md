# Traceability — requirements → work orders → status

Owner: `requirements-analyst` · Last checked 2026-11-22 on branch `week-02` (WO-023) · Kept current every week
(PLAN §4, last line).

Sources are cited by id and paraphrased; they live outside the repository (see `.claude/agents/requirements-analyst.md`).
`tech doc §n` = the updated technical documentation v1.0 (14 Nov). `TC-P1-###` / `OQ-##` = Feature List V2.
`Month-1 §n` / `D-##` = the Month-1 technical documentation. `D#` = PLAN §3 decisions. `OP-##` =
`open-points.md`.

**Status words.** BUILT = merged and the code path exists (still *pending QA* until WO-017 says otherwise —
nothing below is independently verified yet). PARTIAL = some of the requirement exists. MISSING = nothing
exists. BLOCKED = waits on a decision. A stub or an unwired provider is PARTIAL.

## 1. Functional requirements (tech doc §3.1)

| # | Requirement (paraphrased) | Also in | WOs (PLAN §4) | Status 2026-11-22 | Evidence / what is left |
|---|---|---|---|---|---|
| F1 | A visitor finds a product by text, barcode or photo without an account | TC-P1-003, TC-P1-012 | WO-001, 004, 012, 014, 015 (done); WO-007 W4 (image vectors) | BUILT (pending QA) | `backend/app/modules/catalogue/router.py:24` search, `:32` barcode, `:55` photo, `:63` confirm; scan page `frontend/src/pages/Scan.tsx`. Left: image vectors / look-alike photos (WO-007, W4) |
| F2 | One permanent record per product; other sources' listings become aliases | TC-P1-008 | WO-014 (done); WO-003b W3, WO-042 W8 (marketplace listings) | PARTIAL | Barcode aliases and same-product matching: `backend/app/modules/catalogue/identify.py:91-92,165,408`. No marketplace listing exists yet to become an alias (no marketplace source) |
| F3 | Product page shows the passport: recall verdict, certificates, hazard score, the evidence behind each | TC-P1-009/010/011 | WO-004 (partial); WO-031 W4 (certificates); WO-035 W5; WO-039 W6 (trust formula) | PARTIAL | Passport read `catalogue/router.py:77`; citation check → `insufficient_data` `backend/app/modules/screening/service.py:299-327`. Left: certificate import and checker (only sample rows), trust formula provisional (`backend/app/domain/passport.py:16-17`, OP-04), production AI provider (D3, OP-11) |
| F4 | Level 1 by email **and phone** code; Level 2 by ID document and selfie | TC-P1-001 | WO-013 (done); WO-010 + WO-041 W7 | PARTIAL — phone SUPERSEDED (ADR-006, D4); Level 2 BLOCKED (D5) | Email codes `backend/app/modules/identity/router.py:26,39,46`; Level 1 = verified email (ADR-006, migration `20261121120000_level1_email_only`). Level 2: nothing (D5 due W4) |
| F5 | Level 1 users post reviews, photos, hazard flags, fact corrections, each signed | TC-P1-022/023 | WO-006 (done); WO-030 W4 (photos, after WO-007) | PARTIAL | `backend/app/modules/community/router.py:81,124,155`. Photos on reviews/flags missing |
| F6 | Save to a wallet; alerted when a passport changes | TC-P1-013, TC-P1-010 | WO-001 (done); WO-033 W5 (labels, watches, email alerts) | PARTIAL | `backend/app/modules/wallet/router.py:39,51,76,87`; fan-out `backend/app/workers/handlers/alerts.py:16`. In-app only; email alerts wait on D15 |
| F7 | New evidence re-screens; Medium and High go to a human review queue | TC-P1-011 | WO-006 (done); WO-029 W3 (task types, DEF-007), WO-034 W5 (Medium/High → task, High = blocked) | PARTIAL | Re-screen on review via outbox → Worker; uncited dimension → review task `screening/service.py:327`; queue `backend/app/modules/moderation/router.py:21,28,33`. Medium/High routing missing |
| F8 | Useful contributions earn TelCoins after a fraud check; coins spent on listed items | TC-P1-016/017/018 | WO-001 (done); WO-019 W2 (redemptions, D13) | PARTIAL | `backend/app/modules/rewards/router.py:46,64,76,101,152`. Four phase-two redemption items still on sale until WO-019 lands |
| F9 | Admin starts and follows scraping jobs; adds a category by configuration | TC-P1-005 | WO-003 (done for recalls); WO-027 W3 (categories); WO-045 W8 (console) | PARTIAL | `backend/app/modules/ingestion/router.py:25,38,46`; page `frontend/src/pages/DataSources.tsx:27`. Categories are seed data, not configuration |
| F10 | Businesses read passports through an API and get webhooks on status change | TC-P1-012 (contract) | WO-036 W5 (tables), WO-008 W8 | BLOCKED (D6, DEF-002) | Only `POST /screenings`, staff-only until keys exist: `backend/app/modules/screening/router.py:26-28`. No keys, rate limits, webhooks (OP-05) |
| F11 | Every change in an append-only audit log | TC-P1-002 (login attempts) | WO-013 (partial); WO-026 W3 | PARTIAL | `audit()` at `backend/app/core/events.py:42`; 12 call sites in 6 modules (identity, catalogue, community, moderation, screening, ingestion). None in wallet, rewards (redemptions, coin spend), admin source/schedule changes; no request field. Login attempts go to `auth_events` (`identity/service.py:179-206`), not `audit_log` |

## 2. Non-functional requirements (tech doc §3.2)

| Area | Requirement (paraphrased) | WOs | Status | Evidence / what is left |
|---|---|---|---|---|
| Response time | Cached passport < 300 ms; live screening < 3 s text, < 5 s with images (p99) | week-02 baseline; WO-047 W9 (load) | PARTIAL — not measured | 24 h passport cache `backend/app/modules/catalogue/service.py:215`, `core/config.py:43`. No measurement recorded; W2 plan asks for a baseline (`docs/plan/week-02.md`, Performance plan) |
| Availability | Production DB and Redis across two availability zones | WO-050 W10 | BLOCKED (D2, due W3) | Dev is one host (ADR-007); no production |
| Durability — events | No critical event lost on a Redis restart | ADR-002 | BUILT (pending QA) | Transactional outbox `core/events.py:32-39`; publisher `backend/app/workers/publisher.py:24,43`; per-event done key `backend/app/workers/main.py:32-39` |
| Durability — raw | Raw scrapes kept so normalising can re-run | WO-054 (W2, opened 2026-11-22), WO-028 W3 | PARTIAL | Raw payload + SHA-256 kept in `source_records.payload` (`backend/app/modules/ingestion/service.py:86-87`); outside-the-database copy (`payload_storage_key`) never set |
| Security — encryption | At rest and in transit | WO-032 W4, WO-050 W10 | PARTIAL / BLOCKED (D2) | TLS at the edge on dev (Caddy); at-rest encryption of the single host's volume not evidenced here |
| Security — ID documents | Deleted after the match | WO-010 W7 | MISSING (no Level 2 yet; D5) | — |
| Security — least privilege | Least-privilege roles | WO-020 W2 (DEF-006) | PARTIAL | DEF-006: the application's DB role is superuser on dev |
| Traceability — scores | Every score stores model, prompt version, cited evidence | WO-004 | BUILT (pending QA) | `ai_invocations` row for hazard scoring `screening/service.py:274`; citations enforced `:299-327` |
| Traceability — AI calls | Every AI call logged with tokens and cost | WO-035 W5 | PARTIAL | Only hazard scoring writes `ai_invocations`; vision, research, assistant, embedder do not; cost not recorded (PLAN §2) |
| Scalability — services | API and Worker scale separately | ADR-002, ADR-007 | PARTIAL | Separate processes (`backend/app/main.py:27-30`, `backend/app/workers/main.py:79-89`) on one host; independent scaling waits on D2 |
| Scalability — categories | New category needs no deployment | WO-027 W3 | MISSING | Categories fixed in seed data |
| Cost control | AI results cached 24 h; small model for routine work; scraping skips unchanged pages | WO-035 W5 | PARTIAL | Passport cache 24 h (above); unchanged source records skipped `ingestion/service.py:161-170`; per-product per-model AI cache missing; small-model routing = Groq fallback model only (`core/config.py:28-38`) |

## 3. Delivery-process requirements (tech doc §14, §15.5)

| Requirement | WOs | Status | Evidence |
|---|---|---|---|
| Main deploys to dev automatically; merges behind green tests | WO-009 | BUILT (pending QA) | `.github/workflows/pipeline.yml:22-168` (release job publishes `release/dev`) |
| Dependency scan on every commit | WO-020 W2 | PARTIAL (unreviewed merge `706b0f8`) | `.github/workflows/pipeline.yml:22-23` |
| Unfinished features hidden behind `feature_flags` rows | WO-056 (W2, opened 2026-11-22, CT-001) | MISSING | Table only in `db/schema-next/phase3_schema.sql:582`; mapping `backend/app/models/platform.py:72-73`; no reader |
| AI evaluation set on every prompt/model change | WO-057 (W2, 20-case baseline), WO-038 W6 (independent set) | PARTIAL | 12 invented cases `backend/evals/cases.json`; gate at 0.9 `.github/workflows/pipeline.yml:52-53` |
| Contract tests on saved provider responses | WO-049 W9 | PARTIAL | CPSC fixture only (`backend/app/modules/ingestion/cpsc.py:50`) |
| Load test, security pass, restore and replay rehearsals | WO-044 W8, WO-047/048/049 W9 | MISSING (scheduled) | — |

## 4. Feature List V2 items outside the tech doc's phase one
Tracked as OP-15 in `open-points.md`: TC-P1-004 (visual gallery), 007 (commerce feed), 014 (video
verification), 015 (QR labels), 019 (annotation), 020 (Chrome extension), 021 (posts), 024 (price alerts),
025 (community feed), 026 (referrals), 029 (risk timeline). No WO; PLAN §7 lists them as phase two or outside
the ten weeks. TC-P1-002 password reset and Facebook sign-in are gaps with no WO (OP-09, OP-10).
