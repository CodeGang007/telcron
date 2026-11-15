# ADR-003 — Enum values in the backend models are inferred

Date: 2026-11-15 · Status: superseded in intent by WO-011

`backend/app/models/` was written from the ten ERD pages, which name every table, column and enum
type but do not list enum values. The values in `backend/app/models/enums.py` were inferred from the
technical documentation.

Later the same day the real specification turned up on branch `feat/database-schema`
(`docs/database/schema_spec.py`). Compared with it, all 90 tables and their columns match by name and
all 61 enum types exist under the same names, but **54 of the 61 have different values** (for example
`user_role` is `user, moderator, admin` there and `user, safety_reviewer, admin, business` here;
`auth_provider` there has no `password`). The inferred values are therefore known to be wrong, and
they are kept only so the application runs until WO-011 replaces them. Do not build on them.

The first Alembic migration enables `vector`, `pg_trgm` and `citext`. The specification's image also
has PostGIS and `btree_gist`; the local image used here does not ship PostGIS.
