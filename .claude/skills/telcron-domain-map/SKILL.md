---
name: telcron-domain-map
description: Who owns what in Telcron — every backend module, the schema, the frontend and the infrastructure mapped to exactly one engineer agent. Load BEFORE assigning work, before touching a file you are not sure you own, and when routing a defect to an owner.
---

# Domain map — ownership

**Every path has exactly one owner.** A change that needs two owners is a `tech-lead` decomposition with a
frozen contract, not one agent reaching across.

| Owner | Paths | ERD domains |
| --- | --- | --- |
| `platform-identity-engineer` | `backend/app/core/**`, `modules/identity/**` | Identity & Access; Platform, Audit & Operations |
| `catalogue-engineer` | `modules/catalogue/**` (incl. product photos), later `modules/recalls`, `modules/certifications` | Product Catalogue; Recalls; Certifications |
| `data-ai-engineer` | `backend/app/workers/**`, `modules/screening/**`, `modules/ingestion/**`, `modules/research/**`, `modules/assistant/**`, `domain/hazard.py`, `domain/passport.py`, `backend/evals/**`, `services/embedder/**`, later `modules/media` | Sources, Ingestion & Evidence; Media & AI Recognition; Screening, Hazard & Passport |
| `community-rewards-engineer` | `modules/community/**`, `modules/moderation/**`, `modules/wallet/**`, `modules/rewards/**` | Community & Reviews; Digital Wallet; Rewards; Risk Events & Notifications; Pricing |
| `database-engineer` | `db/**`, `docs/database/**`, `backend/app/models/**`, `backend/tests/test_schema_drift.py` | all 14 (schema and its mapping) |
| `frontend-engineer` | `frontend/**` | — |
| `infra-deploy-engineer` | `infra/**`, `docker-compose.yml`, `tools/**`, `.github/**`, `docs/runbooks/**` | — |
| `tech-lead` | `docs/agent-workspace/**`, `docs/decisions/**`, `docs/plan/**`, `.claude/**`, `CLAUDE.md`, the router list in `backend/app/main.py`, `frontend/src/main.tsx`, `frontend/src/components/Layout.tsx` | — |
| `qa-test-engineer` | verdicts; may add tests under `backend/tests/**` | — |
| `browser-qa-engineer` | `e2e/**` (Playwright suites); browser verdicts | — |
| `user-flow-agent` | `docs/product/**`; a WO's `## Acceptance` when asked | — |
| `requirements-analyst` | `docs/requirements/**`; a WO's `## Requirements` when asked | — |
| `technical-writer` | `docs/guides/**` | — |
| `structure-auditor`, `code-quality-auditor` | read-only; reports into the WO log | — |
| `worklog-scribe` | `docs/agent-workspace/WORKLOG.md` | — |
| `project-manager` | Jira project TEL (mirror of the board); `docs/agent-workspace/jira-map.md` | — |

Tests live in `backend/tests/` and are written by the owner of the code they test; browser tests in `e2e/` are
`browser-qa-engineer`'s. Commerce Feed & Personalisation is phase two and has no owner yet; its tables exist and
nothing reads them except `search_queries`.
