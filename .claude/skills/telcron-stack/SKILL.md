---
name: telcron-stack
description: Telcron's exact stack and versions — Python, FastAPI, SQLAlchemy, Alembic, arq, React, Vite, Tailwind — and the choices that are settled. Load before adding a dependency, choosing a library, or when unsure which tool this repo uses for a job.
---

# Stack

**Decided by the user on 2026-11-15: React frontend, FastAPI backend.** Do not introduce Next.js, Hono, Django or
a second ORM.

| Layer | Choice |
| --- | --- |
| Backend | Python 3.13, managed by `uv`. FastAPI, pydantic v2, pydantic-settings |
| Database | PostgreSQL 18 with PostGIS, pgvector, pg_trgm, btree_gist, citext. Schema generated from `docs/database/schema_spec.py`, applied by dbmate. Async SQLAlchemy 2 on asyncpg as a mapping only; no Alembic |
| Queues, cache | Redis 7. arq for jobs |
| Auth | PyJWT (HS256 access tokens), argon2-cffi for passwords |
| Tests, lint | pytest + pytest-asyncio + httpx against real Postgres and Redis. ruff |
| Frontend | React 19, Vite, TypeScript (strict), react-router, Tailwind v4 |
| Local | Docker Compose through `make`: Postgres on :5440 (`DB_PORT`), Redis on :6381. API :4310, web :3200 |
| AWS (dev) | one EC2 t4g.small (Caddy, API, Worker, Redis, PostgreSQL 18, embedder in Docker; ADR-007), Lightsail (Caddy serving the web build), Secrets Manager, S3 |
| CI/CD | GitHub Actions, `.github/workflows/pipeline.yml`. Pull-based release through the `release/dev` branch; no cloud credentials in GitHub. Playwright for the browser tests (`e2e/`) |

- Add a backend dependency with `uv add`, a frontend one with `npm install` in `frontend/`. Say why in the WO.
- Models use `mapped_column` through the helpers in `models/base.py` (`pk`, `fk`, `ts`, `created`, `updated`).
- AI: an OpenAI-compatible model (Groq's free plan) behind the scorer boundary, `StubScorer` as fallback; our
  own embedder for vectors (WO-015). Bedrock is not used while the account is on the Free plan (D3 open).
