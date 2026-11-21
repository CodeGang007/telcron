# Board

Repaired by WO-018 on 2026-11-21: one row per WO file, statuses taken from the files and checked against the
code and `git log`. Week plan: `docs/plan/week-02.md`. Nothing here is `DONE` until a different agent verified it.

## Week 1 (foundation, built 2026-11-15 … 21)

| ID | Title | Owner | Depends | Status |
| --- | --- | --- | --- | --- |
| WO-001 | Foundation: schema, core API, worker, web app, agent workspace | (single session) → qa-test-engineer | — | DONE-PENDING-QA — schema part replaced by WO-011; QA verdict in WO-017 · **QA PASS (run 2)** |
| WO-002 | Deploy dev to AWS | infra-deploy-engineer → security-auditor | WO-011 | DONE-PENDING-QA — superseded in shape by WO-016 (one host); security review in WO-017 · **QA PASS repo-only; security PASS-WITH-FINDINGS** |
| WO-003 | Ingestion: job runner, CPSC recalls; marketplace sources | data-ai-engineer | — | DONE-PENDING-QA for the job runner and recalls; marketplace sources → WO-003b (W3, D7: eBay + Best Buy official APIs) · **QA PARTIAL (marketplace → WO-003b W3)** |
| WO-004 | Hazard scorer, vectors, photo identification | data-ai-engineer → security-auditor | — | PARTIAL — Groq free-plan scorer with stub fallback; photo identification built (`a9002d2`, `067c961`); own embedder (WO-015). Bedrock out (D3) · **QA PARTIAL (board right)** |
| WO-005 | Send verification codes; resend | platform-identity-engineer | — | SUPERSEDED by WO-013 (email + resend); SMS is phase two (D4) · **QA: SUPERSEDED confirmed** |
| WO-006 | Safety-team queue | community-rewards-engineer + frontend-engineer | — | DONE-PENDING-QA — QA verdict in WO-017 · **QA FAIL → DEF-011 (S2), DEF-012; fixes QA PASS 2026-11-22** |
| WO-007 | Media pipeline and photos on reviews and flags | data-ai-engineer | — | OPEN — scheduled W4 (PLAN §4) · **QA: N/A confirmed** |
| WO-008 | Business API: keys, rate limits, webhooks | platform-identity-engineer | DEF-002, D6 | BLOCKED ON HUMAN — W8 · **QA: N/A confirmed** |
| WO-009 | Pipeline: tests on every push, release to dev from `main` | infra-deploy-engineer → qa-test-engineer | WO-002 | DONE-PENDING-QA — QA verdict in WO-017 · **QA PASS** |
| WO-010 | Level 2 identity check | data-ai-engineer + platform-identity-engineer → security-auditor | D5 | BLOCKED ON HUMAN — W7 · **QA: N/A confirmed** |
| WO-011 | Backend converged on the designed schema | database-engineer → qa-test-engineer | DEF-005 | DONE-PENDING-QA — schema author's review still owed (D14) · **QA PARTIAL (phases 2–3 now WO-022; DEF-007)** |
| WO-012 | Web app redesign, scan page, pagination (file written after the fact) | frontend-engineer → qa, browser-qa | — | DONE-PENDING-QA — verdict in WO-017 · **QA FAIL → DEF-013, DEF-014; fixes QA PASS 2026-11-22** |
| WO-013 | Sign-up codes by email; Level 1 = verified email (ADR-006) | platform-identity-engineer → security-auditor | — | DONE-PENDING-QA — live; security review in WO-017 · **QA PASS (local); security → DEF-043/044/048** |
| WO-014 | Product research, photos, same-product matching | data-ai-engineer + catalogue-engineer → security-auditor | — | DONE-PENDING-QA — security review in WO-017 · **QA PASS; security → DEF-041/042/049; DEF-024 → W4 (WO-007)** |
| WO-015 | Own embedder, semantic search, safer alternatives, assistant | data-ai + catalogue + frontend → security-auditor | WO-016 | DONE-PENDING-QA — live · **QA PASS; DEF-022** |
| WO-016 | Dev on one t4g.small (ADR-007) (file written after the fact) | infra-deploy-engineer → security-auditor | — | DONE-PENDING-QA — live; old host and RDS deleted; security review in WO-017 · **QA PASS repo-only; security → DEF-045/047** |

## Week 2 (Sat 21 – Fri 27 Nov)

| ID | Title | Owner | Depends | Status |
| --- | --- | --- | --- | --- |
| WO-017 | Verification sweep of WO-001…016, 018, 024 | qa-test-engineer, browser-qa-engineer, security-auditor | — | DONE-PENDING-QA — sweep complete (run 2, 2026-11-22); verdicts in `verdicts/WO-017-*.md`; last re-check APPROVE WITH NITS (DEF-110, DEF-111 open) |
| WO-018 | Board and WO files repaired | tech-lead | — | DONE-PENDING-QA — this board; WO-012/016 written; WO-004/005/013 status lines corrected. WO-005/DEF-004 close on QA's word · **QA FAIL → DEF-021 (fixed); re-check PASS 2026-11-22; DEF-090 (board agreement) fixed pending QA** |
| WO-019 | Redemptions: phase-one items only, nothing left `processing` | database-engineer → community-rewards-engineer | WO-022, D13 | DONE-PENDING-QA — QA PASS, security PASS (2026-11-22); schema `e49911f`, service `2f40ce3`; DEF-035 (report access) waits on the human |
| WO-020 | Dev hardening: DEF-006; dependency scan in the pipeline | infra-deploy-engineer | — | DONE-PENDING-QA — QA PASS (scan); DEF-006 item 3 closed in repo; items 1, 2, 4 BLOCKED ON HUMAN |
| WO-021 | M1 on dev: sign-up open, a new user verifies | platform-identity-engineer, infra-deploy-engineer | human yes | BLOCKED ON HUMAN |
| WO-022 | Phases 2–3 as migrations | database-engineer | D11 | DONE-PENDING-QA — QA PASS, security PASS (S-18 fixed); `41bdc29` (+ deploy-host lines, same push) |
| WO-023 | Requirements traceability; W1–W2 deliverables check | requirements-analyst | — | DONE-PENDING-QA — `d6dc9a9`; tech-lead review: gap calls agree with the W1–W2 table; M1 "scraping job" = CPSC official API (OP-20, human) |
| WO-024 | Agent skills and agents current | tech-lead | WO-022 | DONE-PENDING-QA — `2212f24`; QA in WO-017 · **QA FAIL → DEF-020 (fixed); re-check PASS 2026-11-22** |
| WO-054 | Raw copies outside the database (S3) for ingestion — code only; enabling on dev waits on the human | data-ai-engineer | — | PARTIAL — code QA PASS + security PASS (off by default; departure from WO text accepted by tech-lead); enabling on dev BLOCKED ON HUMAN |
| WO-055 | Admin shell | frontend-engineer → tech-lead | — | DONE-PENDING-QA — QA PASS, browser PASS |
| WO-056 | Feature flags (CT-001) | platform-identity-engineer, frontend-engineer | — | DONE-PENDING-QA — QA PASS (CT-001 exact), browser PASS |
| WO-057 | AI test set at 20 products (regression baseline) | data-ai-engineer | — | DONE-PENDING-QA — QA PASS (offline harness; no live-model run) |

## Defects

| ID | Title | Owner | Sev | Status |
| --- | --- | --- | --- | --- |
| DEF-001 | Visitor searches cannot be logged (`search_queries.user_id` required) | database-engineer | S4 | RESOLVED — members' searches only |
| DEF-002 | No table for business API keys or webhooks | database-engineer | S3 | OPEN — D6; blocks WO-008 |
| DEF-003 | Alembic downgrade left enum types | database-engineer | S4 | CLOSED — Alembic removed |
| DEF-004 | No way to get new verification codes | platform-identity-engineer | S3 | CLOSED — QA PASS 2026-11-22 |
| DEF-005 | Two schemas for one database; wrong enum values | database-engineer | S2 | CLOSED — QA PASS 2026-11-22 |
| DEF-006 | AWS dev: budget alarm notifies nobody; Lightsail 22; app role superuser; image built on host | infra-deploy-engineer | S3 | OPEN — item 3 closed with evidence 2026-11-22; items 1, 2, 4 prepared, BLOCKED ON HUMAN (WO-020) |
| DEF-007 | Three things the backend wants that the schema lacks | database-engineer | S3 | OPEN — item 1 → WO-029 (W3) |
| DEF-010 | Demo passports score 100 with no assessment | database-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-011 | Moderator can release a fraud hold on own coins | community-rewards-engineer | S2 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-012 | Dismiss leaves holds frozen and flags pending | community-rewards-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-013 | 56 literal colours in components | frontend-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-014 | Reload drops the paged list depth | frontend-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-020 | Skills say Level 1 needs a phone code; D16 not recorded | tech-lead | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-021 | Board and WO files disagree; no WO-018 file | tech-lead | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-022 | Malformed assistant thread_id → 500 | data-ai-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-023 | Domain map lacks owners for research, assistant, moderation, evals, embedder, .claude | tech-lead | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-024 | Member photos stored without safety check or location removal | catalogue-engineer | S3 | OPEN — rescheduled to W4 (WO-007) |
| DEF-060 | Spec still requires phone for Level 1 (users_chk3) | database-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-030 | Product page forgets a saved product after reload | frontend-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-031 | No helpful-vote control in the web app | frontend-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-032 | Each re-screen opens a duplicate evidence task | data-ai-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22; partial unique index proposed (database-engineer, later) |
| DEF-033 | Data sources page mislabels research runs | frontend-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-034 | Header coin balance stale after spending | frontend-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-035 | Paid hazard report is free at the same URL | tech-lead → community-rewards + frontend | S3 | BLOCKED ON HUMAN (product decision: reading (a)/(b), D13) |
| DEF-036 | Unreachable API shown as 'not found' | frontend-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-037 | Home page shows an invented passport | frontend-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-038 | Wallet Remove invisible on phones | frontend-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-040 | Runbook says provider keys leaked, not rotated | infra-deploy-engineer + human | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 (runbook part); rotation PREPARED — BLOCKED ON HUMAN |
| DEF-041 | Research recall carries the product's own name (false near-match) | data-ai-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-042 | Anonymous GET starts Tavily/LLM calls in the API | data-ai-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-043 | Register/sign-in reveal whether an address has an account | platform-identity-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-044 | No rate limits on register, verify, resend, sign-in | platform-identity-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-045 | Runtime DB role owns the database | infra-deploy-engineer | S3 | PREPARED — BLOCKED ON HUMAN |
| DEF-046 | Region/secret name in tracked docs | infra-deploy-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 (runbooks); scripts/config/skill PREPARED — BLOCKED ON HUMAN |
| DEF-047 | Backups deletable by host; seed password on command line; actions by tag | infra-deploy-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 (S-9, S-11); backups (S-8) PREPARED — BLOCKED ON HUMAN |
| DEF-048 | DEV_EXPOSE_CODES unguarded; address logged | platform-identity-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-049 | Research error text to anonymous; no per-user quota; market check | data-ai-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-070 | Research tests reach saferproducts.gov over the network | data-ai-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-080 | Text search reads every product (230–400 ms at 50 000) | catalogue-engineer | S3 | FIXED-PENDING-QA — QA PASS 2026-11-22 (with DEF-110 open) |
| DEF-081 | A register race gives the loser a 500 | platform-identity-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-090 | Board and WO/DEF status lines disagree for 15 week-2 rows | tech-lead | S4 | FIXED-PENDING-QA (WO status lines set; this board brought in line by worklog-scribe 2026-11-22; QA re-check owed) |
| DEF-100 | Signed-in member told to sign in while the API is unreachable | frontend-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-101 | Review queue offers own items' decisions; 38 px buttons on phones | frontend-engineer | S4 | FIXED-PENDING-QA — QA PASS 2026-11-22 |
| DEF-110 | Search's brand list still reads every product when a brand matches; no plan test | catalogue-engineer | S3 | OPEN — routed for W3 (LATERAL query) |
| DEF-111 | Staff with an unreachable API are told to sign in on the admin area | frontend-engineer | S4 | OPEN — routed for W3 |

## Decisions
D1, D4, D7, D8, D11, D13, D16 decided 2026-11-21 (`docs/plan/PLAN.md` §3). Open: D2, D3, D5, D6, D9, D10, D12,
D14, D15 with their due weeks in PLAN §3.
