---
name: telcron-db
description: Rules for Telcron's database — where the schema comes from, how the backend maps onto it, the rules the database enforces, migrations with dbmate and query habits. Load before any query that is not trivial, any model change, any schema change, or any seed change.
---

# Database

**The schema's single source of truth is `docs/database/schema_spec.py`.** `make db-gen` regenerates the
SQL, the ERD and the catalogue in `docs/database/schema-design.md`. Generated files carry a "GENERATED"
header: never hand-edit them. Hand-written rules live in `*_rules.sql`. Read `schema-design.md` before
designing anything: it holds the decisions, the invariants and where each is enforced.

- All three phases are applied by dbmate from `db/migrations/` (WO-022). The backend and schema tests build
  their databases from `db/migrations` + `db/seeds/001_core_reference.sql` only. `make db-next` is retired.
- Never edit an applied migration. Add a new one.

## The backend is a mapping, nothing more

`backend/app/models/` maps the 90 tables for SQLAlchemy. It never creates or alters anything (there is no
Alembic). `backend/tests/test_schema_drift.py` compares it with the live schema and fails on any
difference in tables, columns, types, nullability, defaults, generated columns or enum values.

To change the schema: change `schema_spec.py`, `make db-gen`, add the migration, `make db-test`, then
update the mapping until the drift test is green. `enums.py` is copied from the generated SQL.

Two things about the mapping bite if forgotten:
- The ORM sends an explicit NULL for a column it believes has no default, and omits a column it believes
  the database fills in. So a model's `server_default` must be present exactly where the database has a
  default. The drift test checks both directions.
- Triggers change rows behind the session (a certificate's status, a product's current passport, a
  review's helpful count). Re-read with `populate_existing` or `refresh` before relying on them.

## Rules the database enforces — satisfy them, never work around them

- **Append-only history.** `passports`, `hazard_assessments`, scores, citations, `evidence_items`,
  `source_records`, `risk_events`, `auth_events`, `audit_log` and others refuse UPDATE and DELETE.
  `screenings` may change only while `running`; the ledger only through its status machine.
- **TelCoins** are written only by `coin_earn`, `coin_confirm_due`, `coin_spend`, `coin_redeem`,
  `coin_apply_hold`, `coin_resolve_hold`, `coin_clawback`. They lock the balance row and apply limits,
  the daily cap, the rapid-fire hold and the level bonus.
- **Screening.** A `match` or `near_match` verdict must cite a candidate with that verdict. A scored
  hazard dimension must cite evidence (both checked at commit).
- **Passport.** The version is the next one; the cited screening is completed; a `match` forces badge
  `recalled`; below tier 2 the badge is `needs_information`; tier 2 needs a trust score. A trigger points
  the product at its new passport.
- **Risk fan-out** is `telcron_fanout_risk_event`: who is alerted is its decision.
- CHECK constraints carry business rules too (one verified owner per phone number, an ingested review
  points at its source record, a task priority is 1 to 5). A violation is a bug in the caller.

## Writing queries
- One transaction per request, through the `Db` dependency. It commits before the response is sent.
- Insert children after parents when the foreign key is not mapped: `await db.flush()` between them.
- A row owned by another user is filtered in the `WHERE`, so it is a 404.
- Every list endpoint has a `limit` with a maximum. No unbounded `select`.
- Text search uses `pg_trgm`; vectors use pgvector; identifiers are compared upper-case alphanumeric, and
  a GTIN is stored as 14 digits.
- The backend tests build `telcron_api_test` from the SQL in `db/` on every run.
