# Board

## Foundation run (2026-11-15)

| ID | Title | Owner | Depends | Status |
| --- | --- | --- | --- | --- |
| WO-011 | Converge the backend on the designed database schema | (single session) → database-engineer, qa-test-engineer | DEF-005 | DONE-PENDING-QA — merged into `main` on 2026-11-15 at the human's instruction; gates in the WO log. Not yet reviewed by the schema's author or a second agent |
| WO-001 | Foundation: schema, core API, worker, web app, agent workspace | (single session) → qa-test-engineer | — | DONE-PENDING-QA — its schema part is replaced by WO-011. Not independently verified |
| WO-002 | Deploy dev to AWS (EC2: API + Worker + Redis; RDS; Lightsail web) | (single session) → security-auditor | WO-011 | DONE-PENDING-QA — live since 2026-11-16; gates in the WO log. Not reviewed by security-auditor |
| WO-003 | Ingestion: recall notices from the CPSC (nightly + by hand); marketplace sources later | (single session) → qa-test-engineer | — | DONE-PENDING-QA for recalls — see the WO log |
| WO-004 | AI hazard scoring, photo identification, evals | (single session) → qa-test-engineer | — | PARTIAL — model scorer built (OpenAI-compatible, Groq's free plan) with stub fallback, not switched on (no key yet); evals in `backend/evals` gate the pipeline at 90%; barcode scanning done, photo identification not built. Bedrock blocked: account stays on the Free plan (human's decision) |
| WO-005 | Send the verification codes (email, SMS) and a resend endpoint | platform-identity-engineer → security-auditor | — | OPEN — codes are only shown on screen locally |
| WO-006 | Safety-team queue: confirm or reject flags, accept corrections, resolve fraud holds | (single session) → qa-test-engineer, security-auditor | — | DONE-PENDING-QA — gates in the WO log |
| WO-007 | Media pipeline and photos on reviews and flags | data-ai-engineer | WO-002 | Deploy dev to AWS (EC2: API + Worker + Redis; RDS; Lightsail web) | (single session) → security-auditor | WO-011 | DONE-PENDING-QA — live since 2026-11-16; gates in the WO log. Not reviewed by security-auditor |
| WO-008 | Business API: keys, rate limits, webhooks | platform-identity-engineer | DEF-002 | BLOCKED ON HUMAN — business accounts are not modelled (schema design Q8) |
| WO-009 | Pipeline: tests on every push, release to dev from `main`, browser tests | (single session) → qa-test-engineer | WO-002 | DONE-PENDING-QA — green end to end; see the WO log |
| WO-010 | Level 2 identity check (Textract, Rekognition) | data-ai-engineer + platform-identity-engineer → security-auditor | WO-002 | Deploy dev to AWS (EC2: API + Worker + Redis; RDS; Lightsail web) | (single session) → security-auditor | WO-011 | DONE-PENDING-QA — live since 2026-11-16; gates in the WO log. Not reviewed by security-auditor |

| WO-012 | Web app redesign: open-source components, scan page, animated wallet and rewards, pagination | (single session) → qa-test-engineer | — | DONE-PENDING-QA — live; journey 7 passed |

## Defects

| ID | Title | Owner | Sev | Status |
| --- | --- | --- | --- | --- |
| DEF-005 | Two schemas for one database; 54 of the backend's 61 enum types had the wrong values | database-engineer | S2 | FIXED-PENDING-QA by WO-011 |
| DEF-007 | Three things the backend wants that the schema lacks (raise with its author) | database-engineer | S3 | OPEN — see the defect |
| DEF-001 | `search_queries.user_id` is required, so a visitor's search cannot be logged | database-engineer | S4 | RESOLVED — the backend logs searches of signed-in members only, as the schema requires |
| DEF-002 | No table for business API keys or webhooks | database-engineer | S3 | OPEN — the schema design lists it as Q8; blocks WO-008 |
| DEF-003 | Initial Alembic migration's `downgrade()` leaves the enum types behind | database-engineer | S4 | CLOSED — Alembic removed by WO-011 |
| DEF-004 | Users who leave the sign-up screen cannot get new codes (no resend) | platform-identity-engineer | S3 | OPEN — covered by WO-005 |
| DEF-006 | AWS dev: budget alerts nobody; Lightsail port 22 open; app database role is a superuser; image built on the 1 GB host | infra-deploy-engineer | S3 | OPEN |

## Decisions waiting on the human
1. **Review after the fact.** The convergence and `feat/database-schema` were merged into `main` on 2026-11-15
   at the human's instruction, before the schema's author reviewed how the backend uses it. That review is still owed.
2. **Promote phases 2–3 to migrations?** The backend needs them; today `make db-next` applies them locally.
3. **Passport trust-score arithmetic** (ADR-004; the schema design's Q3). A placeholder is in use.

Decided 2026-11-15: the AWS dev environment stays as built (about USD 33 a month, RDS included).
Decided 2026-11-16: sign-up stays closed on the deployed site, with one seeded admin, until codes can be sent.
