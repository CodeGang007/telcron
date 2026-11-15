# Telcron

Telcron is a consumer product-safety platform. A person scans or searches for a product and sees its
**passport**: recalls, certificates and seven hazard scores, each with the evidence behind it. Verified
members (TelcronID) add reviews and hazard flags and earn TelCoins when a contribution proves useful.

This repository holds the application: `backend/` (FastAPI, one codebase that runs as two services, API
and Worker), `frontend/` (React), and the agent workspace that runs the work.

**Load the `telcron-agent-protocol` skill first in every session**, then `telcron-dev`, then whatever
your task needs. If a session died mid-work, start from `docs/agent-workspace/RESUME-HERE.md`.

## Working here

- Route anything that spans more than one owner, or is stated as an outcome, through `tech-lead`.
  Ownership is `telcron-domain-map`: one path, one owner.
- The board is `docs/agent-workspace/BOARD.md`; the memory is `WORKLOG.md`; decisions are
  `docs/decisions/ADR-*.md`; runbooks are `docs/runbooks/`.
- Only `tech-lead` edits the router list in `backend/app/main.py`, the route table in
  `frontend/src/main.tsx` and the navigation in `frontend/src/components/Layout.tsx`.
- Only `database-engineer` changes `backend/app/models/` or `backend/alembic/`.
- Nobody marks their own work `DONE`. Every reported gate was actually run.

## The database: read this before touching the schema

The schema's source of truth is `docs/database/schema_spec.py` on branch `feat/database-schema` (SQL
migrations with dbmate, rules enforced in the database, tests, the ERD). It is not merged into `main`.
`backend/app/models/` was built from the ERD pictures before that branch was known. All 90 tables and
their columns match by name, but **54 of its 61 enum types have different values**, and it re-implements
in Python what that branch enforces in SQL (the `coin_*` functions, append-only triggers). Converging
on that branch is WO-011, the first thing to do. Until then, do not extend the Alembic schema.

## Running it

```bash
docker compose up -d postgres redis      # PostgreSQL 18 + pgvector on :5436, Redis on :6381
cp .env.example .env.local               # first time; set JWT_SECRET to `openssl rand -hex 32`
cd backend && uv sync && uv run alembic upgrade head && uv run python -m app.seed && cd ..
cd frontend && npm install && cd ..
tools/dev-all.sh                         # API :4310, Worker, web :3200; logs in .dev-logs/
tools/dev-all.sh stop
```

Always run the Worker for real testing: a review is HTTP → outbox → publisher (inside the API) → Redis →
Worker → new passport. Without it nothing is re-screened and no coin is ever confirmed.

## Gates

```bash
cd backend && uv run ruff check . && uv run pytest -q     # needs postgres and redis running
cd frontend && npx tsc --noEmit && npm run build
```

## Non-negotiables

- **Stack (decided 2026-11-15): React frontend, FastAPI backend.** No Next.js, no second ORM.
- Search and passport reads need no account. Contributions need verification Level 1.
- Every hazard score cites evidence that exists. No citation means `insufficient`, never zero.
- Passports, screenings, evidence, the coin ledger and the audit log are append-only. A correction is a
  new row; a re-screen is a new passport version.
- The coin ledger is the truth; the balance moves in the same transaction; every earn has an
  idempotency key. TelCoins are never exchangeable for money.
- A row that belongs to another user is a 404, never a 403.
- A provider client is the only file that talks to its provider and is replaced wholesale in tests. A
  stub or an unwired provider is a named `PARTIAL`, never a `DONE`. `StubScorer` is not AI.
- No literal colours in components; tokens live in `frontend/src/index.css`. The look follows
  testlabhub.com.
- **This repository is public.** No secret, credential, account id, resource id, address or endpoint
  in a tracked file. `.env.local` and `*.local.md` are gitignored.
- Source documents (the platform architecture, the technical documentation, the feature list) live
  OUTSIDE the repository. Local copies under `docs/reference/` are gitignored; never commit them.
- AWS: creating, changing or deleting anything needs the human's explicit yes, with the monthly cost
  stated. The inventory is `docs/runbooks/aws-dev.md`.
- Committing locally never needs permission. Pushing does.
