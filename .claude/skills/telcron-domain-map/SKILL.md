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
| `catalogue-engineer` | `modules/catalogue/**`, later `modules/recalls`, `modules/certifications` | Product Catalogue; Recalls; Certifications |
| `data-ai-engineer` | `backend/app/workers/**`, `modules/screening/**`, `domain/hazard.py`, `domain/passport.py`, later `modules/ingestion`, `modules/media` | Sources, Ingestion & Evidence; Media & AI Recognition; Screening, Hazard & Passport |
| `community-rewards-engineer` | `modules/community/**`, `modules/wallet/**`, `modules/rewards/**`, `domain/coins.py` | Community & Reviews; Digital Wallet; Rewards; Risk Events & Notifications; Pricing |
| `database-engineer` | `backend/app/models/**`, `backend/alembic/**`, reference rows in `seed.py` | all 14 (schema only) |
| `frontend-engineer` | `frontend/**` | — |
| `infra-deploy-engineer` | `infra/**`, `docker-compose.yml`, `tools/**`, `.github/**`, `docs/runbooks/**` | — |
| `tech-lead` | `docs/agent-workspace/**`, `docs/decisions/**`, the router list in `backend/app/main.py`, `frontend/src/main.tsx`, `frontend/src/components/Layout.tsx` | — |
| `qa-test-engineer` | verdicts; may add tests under `backend/tests/**` | — |
| `worklog-scribe` | `docs/agent-workspace/WORKLOG.md` | — |

Tests live in `backend/tests/` and are written by the owner of the code they test. Commerce Feed &
Personalisation is phase two and has no owner yet; its tables exist and nothing reads them except `search_queries`.
