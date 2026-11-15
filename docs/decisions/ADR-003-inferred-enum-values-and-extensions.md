# ADR-003 — Enum values in the backend models were inferred

Date: 2026-11-15 · Status: superseded by ADR-005

The first backend schema was written from the ten ERD pages, which name every table, column and enum
type but not the enum values, so the values were inferred. The real specification then turned up on
branch `feat/database-schema`: 54 of 61 enum types had different values. ADR-005 replaces that schema
with a mapping of the designed one. Nothing inferred remains.
