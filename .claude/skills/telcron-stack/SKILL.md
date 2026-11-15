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
| Database | PostgreSQL 18 with `vector`, `pg_trgm`, `citext`. Async SQLAlchemy 2 on asyncpg. Alembic |
| Queues, cache | Redis 7. arq for jobs |
| Auth | PyJWT (HS256 access tokens), argon2-cffi for passwords |
| Tests, lint | pytest + pytest-asyncio + httpx against real Postgres and Redis. ruff |
| Frontend | React 19, Vite, TypeScript (strict), react-router, Tailwind v4 |
| Local | Docker Compose: Postgres on :5436, Redis on :6381. API :4310, web :3200 |
| AWS (dev) | EC2 t3.micro (API, Worker, Redis in Docker), RDS PostgreSQL 18 db.t4g.micro, Lightsail (web), S3, ECR, Secrets Manager |

- Add a backend dependency with `uv add`, a frontend one with `npm install` in `frontend/`. Say why in the WO.
- Models use `mapped_column` through the helpers in `models/base.py` (`pk`, `fk`, `ts`, `created`, `updated`).
- AI: Amazon Bedrock (Nova for scoring, Titan for vectors) behind the scorer boundary. Not wired yet; the
  account's Bedrock quota is currently zero (see `docs/runbooks/aws-dev.md`).
