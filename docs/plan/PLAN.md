# Telcron — the plan to completion

Status of 2026-11-21 (`main` at `067c961`). Scope comes from the updated technical documentation (v1.0,
14 Nov): §2 scope, §3 requirements, §13 monitoring, §14 testing, §15 delivery plan, §16 risks — cited as
"tech doc §n", paraphrased. Decisions taken since (ADR-006, ADR-007, worklog 2026-11-21) override the document
where they differ; each difference is a decision in §3. Reviewed by `requirements-analyst` on 2026-11-21; its
29 findings are applied.

Week detail: `week-02.md` … `week-10.md`. Index: `README.md`.

## 1. The calendar

Ten one-week iterations from the first commit, **Saturday to Friday**, with the demo to Telcron on the
Friday that closes each week (tech doc §15.5). *Assumption — D1.*

| Week | Dates | Theme | Milestone (tech doc §15.4) |
|---|---|---|---|
| W1 | Sat 14 – Fri 20 Nov | Foundation (done, see §2) | — |
| W2 | Sat 21 – Fri 27 Nov | Verify what exists, repair the board, M1 on dev | **M1 Foundation** |
| W3 | Sat 28 Nov – Fri 4 Dec | Google sign-in, categories by config, first marketplace source, dead letters | — |
| W4 | Sat 5 – Fri 11 Dec | Media pipeline, photos on contributions, certificates, QA environment | **M2 Scan to passport** |
| W5 | Sat 12 – Fri 18 Dec | Wallet watches and email alerts; Medium/High review; AI log and cache | — |
| W6 | Sat 19 – Fri 25 Dec | Evidence loop; evaluation set; trust formula; metrics | **M3 Evidence loop** |
| W7 | Sat 26 Dec – Fri 1 Jan | Level 2 identity (half capacity: holidays) | — |
| W8 | Sat 2 – Fri 8 Jan | Business API, second source, alarms, restore rehearsal | **M4 Feature complete** (in QA) |
| W9 | Sat 9 – Fri 15 Jan | Feature freeze: regression, load, security, replay rehearsal | **M5 Release candidate** |
| W10 | Sat 16 – Fri 22 Jan 2027 | Acceptance, production, launch ingestion, go-live, handover | **M6 Go-live** |

**Capacity.** The tech doc assumes three full-time developers (§2.3, §15.1). The real team is smaller, with
agents doing much of the build; every week below is sized to be cut from the bottom of its list.
**Holidays.** 25 Dec closes W6 and 1 Jan closes W7; W7 is half capacity. If more is lost, the first
candidate to leave the release is the business API — but M4 includes it, so that is decision D12, not a default.

## 2. Where Telcron stands (2026-11-21)

**Done** = merged and live on dev with gates recorded, *not yet independently verified* (see §2.2).
**Partial** = exists, incomplete. **Missing** = not started. **Blocked** = waits on a decision.

| Area | Status | What exists | What is left |
|---|---|---|---|
| Identity | Partial | Register, email codes (Gmail SMTP / SES), resend (`/auth/resend`, sign-in asks for the code), sign-in, refresh, sign-out, roles; Level 1 = verified email (ADR-006); user trust score with provisional deltas (10 at Level 1, moved by moderation); audit entries from identity, identification, ingestion, screening, moderation, community | Google sign-in (decided, not built); phone code (ADR-006 deferred it, tech doc F4 requires it — D4); Level 2 and its +50 trust (WO-010, D5); audit entries for wallet, redemptions/coin spend, admin source and schedule changes, plus the request field (tech doc §12); sign-up still closed on the dev site |
| Catalogue | Done | Products, brands, aliases, same-product matching across barcodes (WO-014), text + meaning search (WO-015), pagination | Categories and manufacturers admin; categories by configuration (F9); the slow-search pattern (`telcron-performance`) |
| Ingestion | Partial | Job runner and admin data-sources page; CPSC recalls nightly and by hand (132 live); research from UK OPSS, openFDA and the web (Tavily); raw payloads with SHA-256 in `source_records`, unchanged repeats skipped; dead-letter list after 5 retries | Two marketplace sources (D7); raw copies for barcode and vision lookups, and outside the database; dead-letter **replay**, alarm and admin view |
| Media | Partial | Barcode identification (UPCitemdb), photo identification (vision model, `067c961`), identification photos stored in S3 and read by Rekognition, shrunk to 1024 px | WO-007: safety check, location-data removal, resizing, image vectors; Worker handlers for the `media` and `identity` queues; photos on reviews and flags |
| Recalls and certificates | Partial | Recall import and matching; recall candidates by meaning; screening already reads certifications and checks | **Certificate import and checker** (FCC, Energy Star; UL/ETL "not checked") — only sample data has rows today |
| Screening and passport | Partial | Recall verdicts; model scorer (Groq free plan, hazard-v3) with stub fallback; **citation check enforced** (uncited → `insufficient_data` and a review task); passport versions; 24 h passport cache; re-screen on review; review queue (WO-006); `ai_invocations` row for hazard scoring (model, prompt, tokens, latency); evals gating at 90 % | Medium/High → review task (needs a schema task type, DEF-007 item 1) and High = blocked + admin alerted (tech doc §7.4); cost on every AI call and a row for vision, Rekognition, research, assistant, embedder; per-product per-model AI result cache (§7.3); an independent evaluation set of 20+ (today's 97 % is a regression baseline); trust formula (ADR-004, D9) |
| Wallet | Partial | Save, list, remove; in-app alerts on passport change; the database fans risk events out to watchers | Labels; a watch API; email alerts (F6) |
| Community | Partial | Reviews (one per product — see open points), helpful votes, hazard flags, fact corrections, safety-team queue | Photos on reviews and flags |
| Rewards | Partial | Earn rules incl. daily sign-in streak (§9.1), ledger, balances, pending → confirmed, fraud holds, levels, badges, leaderboard, coin store | **Bug:** six redemption items on sale; four are phase two, and `data_export` / `invoice_discount` take coins and stay `processing` forever. Only the hazard report and extra watches belong in phase one; extra watches need watches; the hazard report is a print page — acceptable or not (D13) |
| Business API | Blocked | — | DEF-002 tables (D6); keys (Level 2 required, tech doc §8.1), rate limits, passport lookup, `POST /screenings`, webhooks on status change, API docs page (F10) |
| Apps | Partial | Responsive web app with camera scan (WO-012); admin: data sources, review queue | Admin console: jobs, categories, users and roles, fraud holds, dead letters; ID verification screens; API docs page; phone-layout pass |
| Operations | Partial | Dev on one t4g.small (ADR-007); pipeline releasing `main` to dev; backup/restore scripts | QA and production (D2 — tech doc's Terraform/three accounts/Aurora/Fargate vs the Free-plan decision); the 11 alarms and tracing of §13 (none exist; the budget alarm notifies nobody); DEF-006; feature flags (model only, unused) |
| Testing | Partial | Unit, integration against real PostgreSQL/Redis, schema suite, drift, evals, browser journeys, live smoke; one contract fixture (CPSC) | Contract fixtures for UPCitemdb, Groq, Tavily, openFDA/OPSS, Rekognition; dependency scan in the pipeline (tech doc §14: every commit); load test; security pass; restore and replay rehearsals |

**Built beyond the plan** — kept and maintained, not extended until the deliverables are done: product
research with grounding controls (WO-014), own embedder and semantic search, safer alternatives, the product
assistant (WO-015), the redesign.

### 2.2 Debt to pay first
- **Nothing is independently verified.** WO-001–003, 006, 009, 011–016 are DONE-PENDING-QA; security reviews of
  identity (WO-013), deployment (WO-002, 016) and research (WO-014) are owed.
- **The board is wrong.** Rows WO-007 and WO-010 carry WO-002's text; WO-013's file says IN PROGRESS while the
  board says DONE-PENDING-QA; WO-004 says photo identification is not built; WO-005 is OPEN though resend
  shipped; WO-012 and WO-016 have no files.
- Defects: DEF-002 (blocks the business API), DEF-004 (fixed by `/auth/resend` — close after QA), DEF-006,
  DEF-007 (item 1 blocks Medium/High review).
- Phases 2–3 of the schema are applied by `make db-next`, not migrations (D11).
- The schema author's after-the-fact review of how the backend uses the schema is still owed (D14).
- Our branch `feat/agents-and-skills` describes the world before ADR-006/007 in 6 skills and 2 agents.

## 3. Decisions for the human

| # | Decision | Due (end of) | Blocks |
|---|---|---|---|
| D1 | **Decided 2026-11-21:** Week 1 = Sat 14 Nov, go-live week = 16–22 Jan. Still open: holiday availability for W7 | W2 | W7 capacity |
| D2 | QA and production: second/third small host, or the tech doc's target on a paid plan, or other — with monthly cost and which NFRs each option gives up (two zones, encryption at rest, least privilege, separate scaling) | W3 | QA in W4, prod in W10 |
| D3 | AI provider for production (Groq free plan's limits and terms vs Bedrock on a paid plan vs other) and the agreed daily AI budget (§13) | W4 | Cost log, alarms, prod |
| D4 | Phone code for Level 1: reinstate (then start SMS sender registration in W2 — it takes weeks, risk 10; costs money) or have Telcron accept email-only | W2 | W7 |
| D5 | Level 2 provider and the legal basis and retention for ID images (risk 5) | W4 | W7 |
| D6 | Business accounts in the schema (DEF-002, schema Q8) | W4 | W5 tables, W8 API |
| D7 | Which two marketplace sources, API or scraping each, and Telcron's legal confirmation (risk 4) | W2 | W3, W8 |
| D8 | Three launch categories and the countries (risk 3) | W2 | W3 config, evals, launch ingestion |
| D9 | Passport trust-score formula (ADR-004, risk 2) | W5 | W6 |
| D10 | The AI accuracy bar for go-live (§14.1, risk 6) | W6 | M5 |
| D11 | Promote phases 2–3 to migrations | W2 | Clean QA/prod databases |
| D12 | If W7 slips: what leaves the release (business API conflicts with M4) | W6 | M4 |
| D13 | Redemptions: switch off the four phase-two items; is the printable hazard report acceptable | W2 | W2 fix |
| D14 | The schema author's review of the backend's use of the schema | W3 | Confidence in WO-011 |
| D15 | Production email sender (Gmail SMTP vs SES) for codes and alerts | W4 | W5 email alerts |
| D16 | A phone-ready web app (no native apps) is acceptable for launch (risk 9) | W2 | Scope |

Contradictions to keep in `docs/requirements/open-points.md`: session length (`TC-P1-002` 90 min/20 min idle vs
§8.2 1 h/30 d — code follows §8.2); reviews per product (code enforces one, schema allows more).

## 4. Work orders by week

`tech-lead` opens each WO on the week's first day (numbering continues at WO-017) and may merge or split them.
Owners follow `telcron-domain-map`; anything on AWS needs the human's yes with the cost.

| Week | WO | Work | Owner(s) | Needs |
|---|---|---|---|---|
| W2 | WO-017 | Verification sweep: QA verdicts on WO-001…016, browser walk of every journey, security reviews of identity, deployment, research | qa-test-engineer, browser-qa-engineer, security-auditor | — |
| W2 | WO-018 | Repair the board and WO files; write WO-012 and WO-016; close WO-005/DEF-004 on QA's word | tech-lead | WO-017 |
| W2 | WO-019 | Redemptions: only the two phase-one items active; no redemption left `processing` | database-engineer, community-rewards-engineer | D13 |
| W2 | WO-020 | Dev hardening: DEF-006; dependency scan in the pipeline | infra-deploy-engineer | — |
| W2 | WO-021 | M1 on dev: open sign-up on the dev site, a new user verifies by email | platform-identity-engineer, infra-deploy-engineer | human yes |
| W2 | WO-022 | Phases 2–3 promoted to migrations | database-engineer | D11 |
| W2 | WO-023 | `docs/requirements/`: traceability F1–F11 → WOs, open points | requirements-analyst | — |
| W2 | WO-024 | Agent skills brought in line with ADR-006/007 and the code | tech-lead | — |
| W3 | WO-025 | Google sign-in | platform-identity-engineer, frontend-engineer | — |
| W3 | WO-026 | Audit log on every change: wallet, redemptions, admin source/schedule changes; request field | tech-lead → platform-identity, community-rewards, data-ai | — |
| W3 | WO-027 | Categories by configuration (F9) and the categories admin page | catalogue-engineer, data-ai-engineer, frontend-engineer | D8 |
| W3 | WO-003b | First marketplace source behind the per-source adapter | data-ai-engineer | D7 |
| W3 | WO-028 | Dead letters: replay, admin view; raw copies for barcode and vision lookups | data-ai-engineer, frontend-engineer | — |
| W3 | WO-029 | Schema: review-task types for Medium/High (DEF-007 item 1); DEF-007 rest | database-engineer | D14 |
| W4 | WO-007 | Media pipeline: safety check, location removal, resizing, image vectors, `media`/`identity` handlers | data-ai-engineer | — |
| W4 | WO-030 | Photos on reviews and flags (upload, moderation, display) | community-rewards-engineer, frontend-engineer | WO-007 |
| W4 | WO-031 | Certificates: import FCC and Energy Star; checker; UL/ETL "not checked" | catalogue-engineer, data-ai-engineer | — |
| W4 | WO-032 | QA environment; promote M2 to it | infra-deploy-engineer | D2 |
| W5 | WO-033 | Wallet labels, watches (and the extra-watches item), email alerts | community-rewards-engineer, frontend-engineer | D15 |
| W5 | WO-034 | Medium/High → review task; High = blocked + admin alerted | data-ai-engineer | WO-029 |
| W5 | WO-035 | Every AI call logged with cost; per-product per-model result cache | data-ai-engineer | D3 |
| W5 | WO-036 | Business accounts schema (DEF-002) | database-engineer | D6 |
| W6 | WO-037 | Evidence loop end to end: review with photo → re-screen → new passport → alert, in a browser, promoted to QA | data-ai, community-rewards, frontend, browser-qa | WO-030, 033, 034 |
| W6 | WO-038 | Independent evaluation set (20+ products, launch categories), prompt tuning, accuracy report | data-ai-engineer, requirements-analyst | D8, D10 |
| W6 | WO-039 | Trust-score formula implemented | data-ai-engineer, database-engineer | D9 |
| W6 | WO-040 | Application metrics for §13 alarms: uncited rate, image rejections, identity failures, cache hit ratio, fraud holds, AI spend, queue age, dead letters | data-ai, community-rewards, infra | WO-035 |
| W7 | WO-010 | Level 2: ID document + selfie match, images deleted after the match, +50 trust | data-ai-engineer, platform-identity-engineer | D5 |
| W7 | WO-041 | ID verification screens; phone code if D4 = reinstate | frontend-engineer, platform-identity-engineer | D4 |
| W8 | WO-008 | Business API: keys (Level 2), rate limits, passport lookup, `POST /screenings`, webhooks, docs page | platform-identity-engineer, frontend-engineer | WO-036, WO-010 |
| W8 | WO-042 | Second marketplace source; price snapshots | data-ai-engineer (collect), community-rewards-engineer (pricing) | D7 |
| W8 | WO-043 | §13 alarms and dashboards; tracing | infra-deploy-engineer | WO-040 |
| W8 | WO-044 | Database restore rehearsed on QA | infra-deploy-engineer | WO-032 |
| W8 | WO-045 | Admin console complete: jobs, categories, users and roles, fraud holds, dead letters | frontend-engineer | — |
| W9 | WO-046 | Full regression in QA; defect fixing | everyone | freeze |
| W9 | WO-047 | Load test against §3.2 | infra-deploy-engineer, data-ai-engineer | — |
| W9 | WO-048 | Security pass (access rules refused, dependencies, ID data) | security-auditor | — |
| W9 | WO-049 | Dead-letter replay rehearsed; contract fixtures for every provider | data-ai-engineer | — |
| W10 | WO-050 | Production environment and the release-candidate deploy | infra-deploy-engineer | D2 |
| W10 | WO-051 | First ingestion of the launch categories | data-ai-engineer, catalogue-engineer | D8 |
| W10 | WO-052 | Acceptance with Telcron's users; go-live | everyone | M5 |
| W10 | WO-053 | Handover: overview, API reference, admin guide, member help, release notes | technical-writer | — |

Every week: `requirements-analyst` keeps traceability current; `worklog-scribe` writes the worklog;
`tech-lead` keeps the board.

## 5. The weekly gate (Friday, before the demo)
1. `qa-test-engineer` checks each WO's acceptance criteria against the running system, with the revert proof.
2. `browser-qa-engineer` walks every user-visible change: phone width, reload, console, network, the async loop.
3. `security-auditor` on anything touching identity, coins, uploads, ID data, the schema or AWS.
4. Gates run, not asserted: `make db-test`, `make api-test`, `npx tsc --noEmit && npm run build`, `npm run journey`,
   evals; pipeline green on `main`; dev smoke green; from W4, the milestone promoted to QA.
5. New reads meet `telcron-performance` (cached passport < 300 ms; screening < 3 s text, < 5 s images).
6. No stub reported as done.
7. `tech-lead` updates the board, `worklog-scribe` the worklog and resume note; the demo is prepared.

## 6. Go-live exit criteria (tech doc §14.1)
No open Critical or High defect · the evaluation set meets the agreed bar (D10) and no dimension ships without
citations · the load test meets §3.2 · a dead-letter replay and a database restore each rehearsed once (W8, W9).

## 7. Not in this release

**Phase two (tech doc §2.2)** — the tables exist; nothing to build now: native apps and push; commerce feed and
personalisation; social posts, comments, reactions; price alerts (snapshots start in W8); QR labels and video
verification of wallet items; Level 3; referrals; redemption items beyond the hazard report and extra watches.

**Feature List V2, outside the ten weeks:** the Chrome extension; the risk timeline as a product feature.

**Built beyond the plan** (maintain only): the product assistant, safer alternatives and store links, web
research, our own embedder.

**Ideas, not planned:** the tech doc's target infrastructure (Fargate, Aurora, ElastiCache, CloudFront/WAF) if
D2 does not choose it; Bedrock if D3 does not; more categories by configuration after go-live.
