# Board

## Foundation run (2026-11-15)

| ID | Title | Owner | Depends | Status |
| --- | --- | --- | --- | --- |
| WO-011 | **Converge the backend on the real database schema** (`feat/database-schema`) | tech-lead → database, identity, rewards engineers | DEF-005 | BLOCKED ON HUMAN — confirm that branch is the source of truth and who merges it. Do this first |
| WO-001 | Foundation: schema, core API, worker, web app, agent workspace | (single session) → qa-test-engineer | — | DONE-PENDING-QA — gates in the WO log. Not independently verified |
| WO-002 | Deploy dev to AWS (EC2: API + Worker + Redis; database; Lightsail web) | infra-deploy-engineer → security-auditor | WO-011, WO-005 | BLOCKED ON HUMAN — where PostgreSQL runs (cost). Hosts exist and are empty |
| WO-003 | Ingestion: job runner and first marketplace source | data-ai-engineer | WO-007 | BLOCKED ON HUMAN — needs SerpApi/ScraperAPI keys and the legal position on scraping |
| WO-004 | Bedrock scorer, Titan vectors, vector retrieval, photo identification | data-ai-engineer → security-auditor | — | BLOCKED ON HUMAN — the account's Bedrock quota is zero |
| WO-005 | Send the verification codes (email, SMS) and a resend endpoint | platform-identity-engineer → security-auditor | — | OPEN — codes are only shown on screen locally |
| WO-006 | Safety-team queue: confirm or reject flags, resolve tasks and fraud holds | community-rewards-engineer + frontend-engineer | CT-001 (to write) | OPEN |
| WO-007 | Media pipeline and photos on reviews and flags | data-ai-engineer | WO-002 | OPEN |
| WO-008 | Business API: keys, rate limits, webhooks | platform-identity-engineer | DEF-002 | BLOCKED ON HUMAN — no table for keys or webhooks |
| WO-009 | CI on GitHub Actions: ruff, pytest, tsc, build | infra-deploy-engineer | — | OPEN |
| WO-010 | Level 2 identity check (Textract, Rekognition) | data-ai-engineer + platform-identity-engineer → security-auditor | WO-002 | BLOCKED ON HUMAN — legal basis for ID documents |

## Defects

| ID | Title | Owner | Sev | Status |
| --- | --- | --- | --- | --- |
| DEF-005 | Two schemas for one database; 54 of the backend's 61 enum types have the wrong values | database-engineer | S2 | OPEN — WO-011 |
| DEF-001 | `search_queries.user_id` is required in the ERD but anonymous search needs it empty | database-engineer | S4 | OPEN — nullable here; re-check against the spec in WO-011 |
| DEF-002 | No table for business API keys or webhooks | database-engineer | S3 | OPEN — blocks WO-008; re-check against the spec in WO-011 |
| DEF-003 | Initial Alembic migration's `downgrade()` leaves the 61 enum types behind | database-engineer | S4 | OPEN — goes away with WO-011 |
| DEF-004 | Users who leave the sign-up screen cannot get new codes (no resend) | platform-identity-engineer | S3 | OPEN — covered by WO-005 |
| DEF-006 | AWS dev: budget alerts nobody; Lightsail leaves port 22 open | infra-deploy-engineer | S3 | OPEN |

## Decisions waiting on the human
1. **Schema.** Is `feat/database-schema` the source of truth, and who merges it? (WO-011)
2. **Monthly AWS cost.** As built about USD 33; the target is USD 20 to 22. Moving PostgreSQL into Docker
   on the EC2 host and deleting RDS gives about USD 18. See `docs/runbooks/aws-dev.md`.
3. **Passport trust-score formula** and the reward level thresholds (ADR-004). Placeholders are in use.
