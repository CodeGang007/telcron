# Telcron — project context

Telcron is a consumer product-safety platform: "ID.me for products". A product is captured
(photo / barcode / text), identified once into a canonical record, screened against official recall
(CPSC, FDA) and certification (FCC, Energy Star; UL/ETL "not checked") sources with cited evidence,
and issued a versioned Product Passport (tier, badge, trust score). Wallet products are re-screened and
users alerted. Wider scope (Feature List V2): TelCoins rewards, community, commerce feed, price alerts,
risk timeline, Chrome extension.

Source documents live OUTSIDE this repo in `../Resources/` (authoritative: Feature List V2, Platform
Architecture v2, AWS target-state diagram), `../Technical_Documentation/` (Month-1 tech doc) and
`../Notes/`. They conflict in places and are subject to change.

## Decisions so far
- Database: **PostgreSQL 18** + pgvector, pg_trgm, btree_gist, PostGIS, citext (chosen over DynamoDB).
- Auth: **built in-house** — email + password and Google OAuth (not Cognito). Level 1 needs verified email + phone.
- Overall application architecture is being redesigned by a teammate — don't assume services/infra beyond the DB.
- Local dev: Docker Compose (`make db-up`), Postgres on **localhost:5433** (5432 is the system Postgres).

## Database
- Design doc: `docs/database/schema-design.md` · ERD: `docs/database/telcron-erd.drawio`.
- Single source of truth: `docs/database/schema_spec.py` → `make db-gen` regenerates SQL, ERD and catalogue.
  Generated files carry a "GENERATED" header — never hand-edit them; hand-written rules are `*_rules.sql`.
- Phase 1 (core, 38 tables) is in `db/migrations/` (dbmate). Phases 2–3 are designed and tested in
  `db/schema-next/` but not applied. Never edit an applied migration — add a new one.
- History tables are append-only (DB-enforced); TelCoins writes go only through `coin_*` functions.
- `make db-test` must pass after any schema change; add a test for every new invariant.

## Commands
`make help` lists everything: db-up, db-migrate, db-seed, db-sample, db-reset, db-psql, db-test, db-test-perf, db-gen.
