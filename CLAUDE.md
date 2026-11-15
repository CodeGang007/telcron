# Telcron — project context

Telcron is a consumer product-safety platform: "ID.me for products". A product is captured
(photo / barcode / text), identified once into a canonical record, screened against official recall
(CPSC, FDA) and certification (FCC, Energy Star; UL/ETL "not checked") sources with cited evidence,
and issued a versioned Product Passport (tier, badge, trust score). Wallet products are re-screened and
users alerted. Wider scope (Feature List V2): TelCoins rewards, community, commerce feed, price alerts,
risk timeline, Chrome extension.

Source documents live OUTSIDE this repo in `../Resources/` (authoritative: Feature List V2, Platform
Architecture v2, AWS target-state diagram), `../Technical_Documentation/` (Month-1 tech doc) and
`../Notes/`. They conflict in places and are subject to change. Local copies under `docs/reference/`
are gitignored; never commit them.

**Load the `telcron-agent-protocol` skill first in every session**, then `telcron-dev`, then whatever
your task needs. If a session died mid-work, start from `docs/agent-workspace/RESUME-HERE.md`.

## Decisions so far
- Database: **PostgreSQL 18** + pgvector, pg_trgm, btree_gist, PostGIS, citext (chosen over DynamoDB).
- Auth: **built in-house** — email + password and Google OAuth (not Cognito). Level 1 needs verified email + phone.
- Application: **React frontend, FastAPI backend** (decided 2026-11-15). One Python codebase runs as two
  services, the API and a Worker, joined by Redis queues and a transactional outbox. See "Application".
- Local dev: Docker Compose (`make up`), Postgres on **localhost:5433** (5432 is the system Postgres; set
  `DB_PORT` in `.env` if 5433 is taken too), Redis on 6381.

## Database
- Design doc: `docs/database/schema-design.md` · ERD: `docs/database/telcron-erd.drawio`.
- Single source of truth: `docs/database/schema_spec.py` → `make db-gen` regenerates SQL, ERD and catalogue.
  Generated files carry a "GENERATED" header — never hand-edit them; hand-written rules are `*_rules.sql`.
- Phase 1 (core, 38 tables) is in `db/migrations/` (dbmate). Phases 2–3 are designed and tested in
  `db/schema-next/` but not applied. Never edit an applied migration — add a new one.
- History tables are append-only (DB-enforced); TelCoins writes go only through `coin_*` functions.
- `make db-test` must pass after any schema change; add a test for every new invariant.
- The application never creates or alters a table. `backend/app/models/` is a mapping of this schema, and
  `backend/tests/test_schema_drift.py` fails when the two disagree. Change the spec first, then the mapping.
- The backend uses tables from phases 2–3. Until those are promoted to migrations, `make db-next` applies
  `db/schema-next/` to the LOCAL database, and the backend tests apply it to their own.

## Application
- Layout: `backend/app/` — `core` (config, db, security, auth dependencies, the outbox), `domain` (pure
  rules with exact answers), `models` (the mapping), `modules/<name>` (router, service, schemas),
  `workers` (outbox publisher, queue handlers). `frontend/src/` — `lib`, `components`, `pages`.
- Route anything that spans more than one owner, or is stated as an outcome, through `tech-lead`.
  Ownership is `telcron-domain-map`: one path, one owner.
- The board is `docs/agent-workspace/BOARD.md`; the memory is `WORKLOG.md`; decisions are
  `docs/decisions/ADR-*.md`; runbooks are `docs/runbooks/`.
- Only `tech-lead` edits the router list in `backend/app/main.py`, the route table in
  `frontend/src/main.tsx` and the navigation in `frontend/src/components/Layout.tsx`.
- Nobody marks their own work `DONE`. Every reported gate was actually run.

```bash
cp .env.example .env        # set JWT_SECRET to `openssl rand -hex 32`
make app-db                 # Postgres + Redis, migrations, reference data, phases 2-3, demo data
cd frontend && npm install && cd ..
make dev                    # API :4310, Worker, web :3200; logs in .dev-logs/   ·   make dev-stop
```

Always run the Worker for real testing: a review is HTTP → outbox → publisher (inside the API) → Redis →
Worker → new passport. Without it nothing is re-screened and no coin is ever confirmed.

Gates: `make api-test` (backend lint and tests), `make db-test` (schema tests),
`cd frontend && npx tsc --noEmit && npm run build`, and with the stack running
`cd e2e && npm run journey` (the member's journey in a browser).

**A push to `main` is a release.** `.github/workflows/pipeline.yml` runs all of those gates and, when they
pass, publishes the build to the `release/dev` branch; the two AWS hosts poll that branch and deploy
themselves; the run then checks the live site. See `docs/runbooks/aws-dev.md`.

## Non-negotiables
- Search and passport reads need no account. Contributions need verification Level 1.
- The database's rules are the rules. The application orders its writes to satisfy them and never works
  around a trigger, a check or a `coin_*` function.
- Every hazard score cites evidence that exists. No citation means `insufficient_data`, never zero.
- A row that belongs to another user is a 404, never a 403.
- A provider client is the only file that talks to its provider and is replaced wholesale in tests. A
  stub or an unwired provider is a named `PARTIAL`, never a `DONE`. `StubScorer` is not AI.
- No literal colours in components; tokens live in `frontend/src/index.css`. The look follows
  testlabhub.com.
- **This repository is public.** No secret, credential, account id, resource id, address or endpoint
  in a tracked file. `.env` and `*.local.md` are gitignored.
- AWS: creating, changing or deleting anything needs the human's explicit yes, with the monthly cost
  stated. The inventory is `docs/runbooks/aws-dev.md`.
- Committing locally never needs permission. Pushing does, and pushing `main` deploys to dev: show the
  human what will go out and get an explicit yes. Never push to `release/dev` by hand.

## Commands
`make help` lists everything: db-up, db-migrate, db-seed, db-sample, db-reset, db-psql, db-test, db-test-perf,
db-gen, and for the application: up, db-next, app-db, api-test, dev, dev-stop.
