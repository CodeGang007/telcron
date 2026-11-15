---
name: telcron-db
description: Rules for Telcron's database — the 90-table ERD, append-only tables, enums, migrations with Alembic, indexes and query habits. Load before any query that is not trivial, any model change, any migration, or any seed change.
---

# Database

**The schema's source of truth is `docs/database/schema_spec.py` on branch `feat/database-schema`** (SQL
migrations with dbmate, rules enforced in the database, a test suite, the ERD). It is not merged into `main`
yet. `backend/app/models/` was built from the ERD pictures before that branch was known: all 90 tables and
their columns match by name, but 54 of its 61 enum types have different values, and it re-implements in
Python what that branch enforces in SQL (the `coin_*` functions, append-only triggers). That is DEF-005;
converging is WO-011. Until then **do not extend the Alembic schema**. Only `database-engineer` changes
models or migrations.

## Changing the schema
```bash
cd backend
uv run alembic revision --autogenerate -m "what_changed"   # then READ the file; autogenerate misses things
uv run alembic upgrade head
uv run alembic downgrade -1 && uv run alembic upgrade head  # prove the downgrade works
```
- A deviation from the spec is a `DEF-###` with its reason. Known: DEF-001 (`search_queries.user_id` nullable).
- Enum values here were inferred (ADR-003) and mostly differ from the spec (DEF-005). Do not add to them.
- Circular foreign keys use `use_alter=True` in `fk()`.

## Writing queries
- One transaction per request, through the `Db` dependency. It commits before the response is sent.
- Lock before you read-then-write money or counters: `select(...).with_for_update()`. The coin balance row is
  the lock that serialises a user's earns.
- Never update an append-only table: `source_records`, `evidence_items`, `screenings`, `screening_matches`,
  `hazard_assessments`, `hazard_dimension_scores`, `hazard_score_citations`, `passports`, `passport_evidence`,
  `coin_ledger_entries`, `audit_log`, `auth_events`, `trust_score_events`, `certification_checks`,
  `price_snapshots`, `risk_events`, `ai_invocations`.
- A row owned by another user is filtered in the `WHERE`, so it is a 404.
- Every list endpoint has a `limit` with a maximum. No unbounded `select`.
- Text search uses `pg_trgm` (`similarity`, `word_similarity`); vectors use pgvector, dimension 1024.
- Tests run in their own database, `telcron_test`, created fresh per run.
