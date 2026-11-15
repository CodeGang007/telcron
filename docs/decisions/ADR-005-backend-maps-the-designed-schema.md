# ADR-005 — The backend maps the designed schema and creates nothing

Date: 2026-11-15 · Status: accepted (merged into `main` 2026-11-15; review by the schema's author still owed)

The database is designed in `docs/database/schema_spec.py` and applied by dbmate SQL migrations, with
rules enforced in the database and its own test suite. The backend adopts it as is:

- Alembic and the backend's own migration are removed. SQLAlchemy never creates or alters a table.
- `backend/app/models/` is a mapping. `backend/tests/test_schema_drift.py` fails on any difference in
  tables, columns, types, nullability, defaults, generated columns or enum values.
- The backend's tests build their database from the SQL in `db/`, in the order the schema's own tests use.
- Rules the database owns are not repeated in Python: TelCoins go through the `coin_*` functions, risk
  alerts through `telcron_fanout_risk_event`, helpful counts and current passports through triggers.
- The backend needs tables from phases 2–3, which are designed but not yet migrations. `make db-next`
  applies `db/schema-next/` to a local database. Promoting them is the database owner's decision.

What the database caught while converging, each now fixed and covered by a test: a rotated session
could outlive its family; two accounts could verify one phone number; a certificate's status was read
stale after a trigger changed it.
