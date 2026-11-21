# Board

Repaired by WO-018 on 2026-11-21: one row per WO file, statuses taken from the files and checked against the
code and `git log`. Week plan: `docs/plan/week-02.md`. Nothing here is `DONE` until a different agent verified it.

## Week 1 (foundation, built 2026-11-15 … 21)

| ID | Title | Owner | Depends | Status |
| --- | --- | --- | --- | --- |
| WO-001 | Foundation: schema, core API, worker, web app, agent workspace | (single session) → qa-test-engineer | — | DONE-PENDING-QA — schema part replaced by WO-011; QA verdict in WO-017 |
| WO-002 | Deploy dev to AWS | infra-deploy-engineer → security-auditor | WO-011 | DONE-PENDING-QA — superseded in shape by WO-016 (one host); security review in WO-017 |
| WO-003 | Ingestion: job runner, CPSC recalls; marketplace sources | data-ai-engineer | — | DONE-PENDING-QA for the job runner and recalls; marketplace sources → WO-003b (W3, D7: eBay + Best Buy official APIs) |
| WO-004 | Hazard scorer, vectors, photo identification | data-ai-engineer → security-auditor | — | PARTIAL — Groq free-plan scorer with stub fallback; photo identification built (`a9002d2`, `067c961`); own embedder (WO-015). Bedrock out (D3) |
| WO-005 | Send verification codes; resend | platform-identity-engineer | — | SUPERSEDED by WO-013 (email + resend); SMS is phase two (D4) |
| WO-006 | Safety-team queue | community-rewards-engineer + frontend-engineer | — | DONE-PENDING-QA — QA verdict in WO-017 |
| WO-007 | Media pipeline and photos on reviews and flags | data-ai-engineer | — | OPEN — scheduled W4 (PLAN §4) |
| WO-008 | Business API: keys, rate limits, webhooks | platform-identity-engineer | DEF-002, D6 | BLOCKED ON HUMAN — W8 |
| WO-009 | Pipeline: tests on every push, release to dev from `main` | infra-deploy-engineer → qa-test-engineer | WO-002 | DONE-PENDING-QA — QA verdict in WO-017 |
| WO-010 | Level 2 identity check | data-ai-engineer + platform-identity-engineer → security-auditor | D5 | BLOCKED ON HUMAN — W7 |
| WO-011 | Backend converged on the designed schema | database-engineer → qa-test-engineer | DEF-005 | DONE-PENDING-QA — schema author's review still owed (D14) |
| WO-012 | Web app redesign, scan page, pagination (file written after the fact) | frontend-engineer → qa, browser-qa | — | DONE-PENDING-QA — verdict in WO-017 |
| WO-013 | Sign-up codes by email; Level 1 = verified email (ADR-006) | platform-identity-engineer → security-auditor | — | DONE-PENDING-QA — live; security review in WO-017 |
| WO-014 | Product research, photos, same-product matching | data-ai-engineer + catalogue-engineer → security-auditor | — | DONE-PENDING-QA — security review in WO-017 |
| WO-015 | Own embedder, semantic search, safer alternatives, assistant | data-ai + catalogue + frontend → security-auditor | WO-016 | DONE-PENDING-QA — live |
| WO-016 | Dev on one t4g.small (ADR-007) (file written after the fact) | infra-deploy-engineer → security-auditor | — | DONE-PENDING-QA — live; old host and RDS deleted; security review in WO-017 |

## Week 2 (Sat 21 – Fri 27 Nov)

| ID | Title | Owner | Depends | Status |
| --- | --- | --- | --- | --- |
| WO-017 | Verification sweep of WO-001…016 | qa-test-engineer, browser-qa-engineer, security-auditor | — | DISPATCHED |
| WO-018 | Board and WO files repaired | tech-lead | — | DONE-PENDING-QA — this board; WO-012/016 written; WO-004/005/013 status lines corrected. WO-005/DEF-004 close on QA's word |
| WO-019 | Redemptions: phase-one items only, nothing left `processing` | database-engineer → community-rewards-engineer | WO-022, D13 | OPEN |
| WO-020 | Dev hardening: DEF-006; dependency scan in the pipeline | infra-deploy-engineer | — | DISPATCHED (code part); AWS part waits on the human |
| WO-021 | M1 on dev: sign-up open, a new user verifies | platform-identity-engineer, infra-deploy-engineer | human yes | BLOCKED ON HUMAN |
| WO-022 | Phases 2–3 as migrations | database-engineer | D11 | DISPATCHED |
| WO-023 | Requirements traceability; W1–W2 deliverables check | requirements-analyst | — | DISPATCHED |
| WO-024 | Agent skills and agents current | tech-lead | WO-022 | OPEN |

## Defects

| ID | Title | Owner | Sev | Status |
| --- | --- | --- | --- | --- |
| DEF-001 | Visitor searches cannot be logged (`search_queries.user_id` required) | database-engineer | S4 | RESOLVED — members' searches only |
| DEF-002 | No table for business API keys or webhooks | database-engineer | S3 | OPEN — D6; blocks WO-008 |
| DEF-003 | Alembic downgrade left enum types | database-engineer | S4 | CLOSED — Alembic removed |
| DEF-004 | No way to get new verification codes | platform-identity-engineer | S3 | FIXED-PENDING-QA — `POST /auth/resend` (WO-013) |
| DEF-005 | Two schemas for one database; wrong enum values | database-engineer | S2 | FIXED-PENDING-QA — WO-011 |
| DEF-006 | AWS dev: budget alarm notifies nobody; Lightsail 22; app role superuser; image built on host | infra-deploy-engineer | S3 | OPEN — WO-020 |
| DEF-007 | Three things the backend wants that the schema lacks | database-engineer | S3 | OPEN — item 1 → WO-029 (W3) |

## Decisions
D1, D4, D7, D8, D11, D13, D16 decided 2026-11-21 (`docs/plan/PLAN.md` §3). Open: D2, D3, D5, D6, D9, D10, D12,
D14, D15 with their due weeks in PLAN §3.
