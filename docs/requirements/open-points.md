# Open points — contradictions, gaps and decisions

Owner: `requirements-analyst` · Last checked 2026-11-22 (WO-023). The analyst records; it never decides. An
open point is removed only when an ADR or the human settles it; a settled one stays here, marked DECIDED, with
where it was settled. Precedence when sources disagree: `telcron-business-rules` (database > reference data >
ADRs > Feature List V2 > tech doc > Architecture v2 / Month-1 doc).

Citations as in `traceability.md`. Paraphrased; no source text is reproduced.

## 1. Contradictions between sources

| OP | Topic | Source A says | Source B says | The code today | State | Decision by / due |
|---|---|---|---|---|---|---|
| OP-01 | Data collection | Feature List V2 out-of-scope item 9 and TC-P1-005: official APIs only, no scraping | Tech doc §6.2 and §2.3: SerpApi and ScraperAPI scraping | No marketplace source yet; recalls via CPSC's API | **DECIDED** D7 (2026-11-21): eBay and Best Buy through official APIs. Still open: Telcron's written legal OK per source, recorded before each is enabled (tech doc §16 risk 4) | human; before WO-003b is enabled (W3) |
| OP-02 | Session length | TC-P1-002: 90 min absolute, 20 min idle, configurable | Tech doc §8.2: 1 h access token, 30-day rotating refresh token | Follows §8.2: `backend/app/core/config.py:20-21` | OPEN — no due week in PLAN | human |
| OP-03 | Reviews per product | Schema/reference data: several reviews per product, `review` rule pays up to five | Tech doc §9.1: one review per product per user | API refuses a second: `backend/app/modules/community/router.py:90` (`409 already_reviewed`) | OPEN — no due week in PLAN | human |
| OP-04 | Passport trust-score formula | Tech doc §7.5 and §16 risk 2: not defined, agree in week 1 | Month-1 §4.3 (D-07, proposed): recall 60 % · certification 30 % · hazard 10 %, badge rules win over the number | Provisional 40/20/40, `formula_version provisional-0`: `backend/app/domain/passport.py:16-17` (ADR-004). The Month-1 proposal is not mentioned in ADR-004 | OPEN — D9 | human, W5 (WO-039 W6) |
| OP-05 | Business API | Tech doc §2.1, F10, §8.1: phase one; keys need Level 2 | Schema: no tables for keys or webhooks (DEF-002). Feature List V2 out-of-scope item 2 excludes a business login/dashboard (not the API) | `POST /screenings` staff-only: `backend/app/modules/screening/router.py:26-28` | OPEN — D6 (schema), D12 (what leaves if W7 slips) | human, D6 W4, D12 W6 |
| OP-06 | Hosting | Tech doc §4: Fargate, Aurora, ElastiCache, CloudFront/WAF, three accounts by Terraform. TC-P1-027/028: ECS, one isolated account per environment, Dev→QA→Prod with approval gates | Month-1 §5: serverless (Lambda, API Gateway), Dev account only | Dev = one EC2 host, Docker Compose, shell scripts (`infra/aws/`), ADR-007 | Dev **DECIDED** (ADR-007). QA and production OPEN — D2 | human, W3 |
| OP-07 | Level 1 phone code | TC-P1-001, tech doc §8.1 / F4: email and phone | ADR-006: email only | Email only (migration `20261121120000_level1_email_only`) | **DECIDED** D4 (2026-11-21): phone is phase two | — |
| OP-08 | Sign-in provider | TC-P1-002: AWS Cognito-backed JWT | Project decision (CLAUDE.md "Decisions so far"): in-house email + password and Google | In-house: `backend/app/modules/identity/` | **DECIDED** by the human (no ADR records it — tech-lead may want one) | — |
| OP-09 | Social sign-in providers | TC-P1-001/002: Facebook and Google | Project decision: Google only (WO-025, W3) | Neither built | OPEN — Facebook has no WO and no recorded decision | human |
| OP-10 | Password reset | TC-P1-002: reset by emailed link, old password invalid afterwards | Tech doc §8 and §11: not mentioned | No route (`backend/app/modules/identity/router.py:26-69`) | OPEN gap — no WO schedules it | tech-lead (schedule) / human (scope) |
| OP-11 | AI provider | TC-P1-011, tech doc §4.2/§7.2, Month-1 D-05: Amazon Bedrock (Nova, Titan, Guardrails) | — | Groq free plan, Gemini fallback, own embedder: `backend/app/core/config.py:28-38`. No Guardrails equivalent | OPEN — D3 | human, W4 |
| OP-12 | Database | Architecture v2 and Month-1 §7: DynamoDB | Tech doc §1.3/§5.4: PostgreSQL + Redis | PostgreSQL 18 | **DECIDED** (project decision; tech doc agrees) | — |
| OP-13 | Recall sources and cadence | TC-P1-010: FDA Recall API and recalls.gov/CPSC; near-real-time sync, not only fixed schedules | Month-1 §3.5/§9: CPSC daily by default, openFDA optional by category; D-08 nightly | CPSC nightly at 03:00 (`backend/app/workers/main.py:87`); openFDA only through research | OPEN — cadence and FDA's place after D8's categories | human |
| OP-14 | Certificate sources | TC-P1-009: query FCC, UL, ETL and Energy Star | OQ-05: access to UL/ETL/FCC/Energy Star not confirmed; Month-1 §3.5: UL/ETL reported "not checked" | No certificate import yet (WO-031 W4) | OPEN — OQ-05 | human (Telcron) before W4 |
| OP-15 | Feature List V2 phase-one items the tech doc defers | TC-P1-004, 007, 014, 015, 019, 020, 021, 024, 025, 026, 029 in the Feature List | Tech doc §2.2 phase two; PLAN §7 phase two or outside the ten weeks | Tables exist for most; nothing built | OPEN — PLAN §7 is the plan's position, not a recorded human decision (only D16 native apps is) | human (Telcron's written OK) |
| OP-16 | Redemption items | TC-P1-017: full hazard report as a downloadable PDF, among others | Tech doc §9.4: two items in phase one. Reference data: six items | Six on sale (WO-019 fixes) | **DECIDED** D13 (2026-11-21): two items; the printable page stands in for the PDF | — |
| OP-17 | Hazard total's denominator | Tech doc §7.4: divide by 11, the sum of all seven weights | `telcron-business-rules` §3: divide by the weights of the dimensions actually scored (an uncited one drops out) | Scored weights only: `backend/app/domain/hazard.py:18-29` | OPEN — the code's rule is sound for honesty but no ADR ratifies the departure | human / tech-lead (ADR) |
| OP-18 | Alert threshold | Feature List V2 / `scoring_contexts.alert_threshold`: 80 | Tech doc §7.4: 60+ is High, blocked and admin alerted | Bands from `scoring_bands`; Medium/High routing not built (WO-034) | OPEN — both configurable; which one alerts users is undecided | human, before WO-034 (W5) |
| OP-19 | Launch categories | Month-1 D-01: proof-of-concept seed categories (small appliances such as blenders, mini-fridges) | Tech doc §2.3: three categories, chosen in week 1 | Seed data | **DECIDED** D8 (2026-11-21): US only; children's products, small kitchen appliances, chargers and small electronics | — |
| OP-20 | M1 wording | Tech doc §15.4 M1: a *scraping* job fills `source_records` | D7 / Feature List V2: no scraping | A CPSC recall job (official API) fills `source_records` | OPEN — does an official-API ingestion job meet M1? | tech-lead, W2 |
| OP-21 | Schema rollout | Tech doc §2.2 and §15.3 W1: all tables created by the first migrations | Repo: 38 core tables migrated; phases 2–3 only via `make db-next` | — | **DECIDED** D11 (2026-11-21): promote in W2 (WO-022, in progress) | — |
| OP-22 | Native apps | TC-P1 out-of-scope 8 and tech doc §2.2 agree: web only | — | Phone-ready web app | **DECIDED** D16 (2026-11-21); Telcron's written OK still to be recorded | human |

## 2. Gaps (a requirement with no WO)

| Gap | Source | Note |
|---|---|---|
| Password reset | TC-P1-002 | OP-10 |
| Facebook sign-in | TC-P1-001/002 | OP-09 |
| Terraform for any environment | tech doc §4.4, §15.3 W1 | Depends on D2; no WO names it (WO-032, WO-050 name environments only) |
| Feature flags | tech doc §15.5 | Was unscheduled in PLAN §4; WO-056 opened 2026-11-22 (W2). Its table is phase 3, so it also depends on WO-022 |
| Raw copies outside the database | tech doc §6.2 step 3, §15.3 W2 | Was unscheduled (PLAN WO-028 covers barcode/vision only); WO-054 opened 2026-11-22 (W2) |
| Admin shell | tech doc §15.3 W2 (C) | PLAN WO-045 W8 is the full console; WO-055 opened 2026-11-22 (W2) |
| AI test set of 20 | tech doc §15.3 W1 (B) | 12 cases exist; WO-057 opened 2026-11-22 (W2); independent set stays WO-038 W6 |
| Dev runbook says sign-up is closed because codes cannot be sent (WO-005) | — | Stale reason: email codes ship since WO-013 (`docs/runbooks/aws-dev.md:139 (line as of 2026-11-22; file being edited by WO-020)`). Owner: infra-deploy-engineer |

## 3. Decisions D1–D16 (PLAN §3) — state on 2026-11-22

| D | Decision | State | Due (end of) | Blocks |
|---|---|---|---|---|
| D1 | Calendar: W1 = Sat 14 Nov; go-live 16–22 Jan; W7 full week | DECIDED 2026-11-21 | W2 | — |
| D2 | QA and production shape and cost (OP-06) | OPEN | W3 | WO-032 W4, WO-050 W10; NFR availability, encryption, scaling |
| D3 | Production AI provider and daily AI budget (OP-11) | OPEN | W4 | WO-035 W5, alarms, prod |
| D4 | Phone code for Level 1 (OP-07) | DECIDED 2026-11-21: phase two | W2 | — |
| D5 | Level 2 provider, legal basis and retention for ID images | OPEN | W4 | WO-010 W7 |
| D6 | Business accounts in the schema (DEF-002, OP-05) | OPEN | W4 | WO-036 W5, WO-008 W8 |
| D7 | Marketplace sources (OP-01) | DECIDED 2026-11-21: eBay + Best Buy official APIs; legal OK per source outstanding | W2 | WO-003b W3, WO-042 W8 |
| D8 | Countries and launch categories (OP-19) | DECIDED 2026-11-21 | W2 | — |
| D9 | Trust-score formula (OP-04) | OPEN | W5 | WO-039 W6 |
| D10 | AI accuracy bar for go-live | OPEN | W6 | WO-038, M5 |
| D11 | Phases 2–3 as migrations (OP-21) | DECIDED 2026-11-21 | W2 | — |
| D12 | What leaves the release if W7 slips | OPEN | W6 | M4 |
| D13 | Redemption items (OP-16) | DECIDED 2026-11-21 | W2 | — |
| D14 | Schema author's review of the backend's use of the schema | OPEN | W3 | WO-029, confidence in WO-011 |
| D15 | Production email sender (Gmail SMTP vs SES) | OPEN | W4 | WO-033 W5 |
| D16 | Web app only; native apps phase two (OP-22) | DECIDED 2026-11-21; Telcron's written OK to record | W2 | — |

**Count:** 22 contradictions (OP-01…OP-22): 9 decided (OP-01, 06 for dev, 07, 08, 12, 16, 19, 21, 22),
13 open. Decisions: 7 decided (D1, D4, D7, D8, D11, D13, D16), 9 open (D2, D3, D5, D6, D9, D10, D12, D14, D15).
Open points with no due week: OP-02, 03, 09, 10, 13, 15, 17.
