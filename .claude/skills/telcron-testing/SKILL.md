---
name: telcron-testing
description: How Telcron is tested — the levels (pure rules, integration against real PostgreSQL and Redis, the schema's own suite, drift, contract tests on recorded provider responses, the AI evaluation set, browser journeys, load, security), the tests every change must carry (access 401/403/404, pay-once, append-only, citations), the revert proof, and what not to test. Load before writing or reviewing tests, and before claiming a gate passed.
---

# Testing

A test proves a **behaviour a person relies on**, against the real database, and goes red when that behaviour
breaks. Tech doc §14 is the plan; this is how it maps onto the repository.

## The levels
| Level | Where | Runs against | When |
|---|---|---|---|
| Pure rules | `backend/tests/test_rules.py` | nothing — `app/domain/*` functions with exact answers (hazard formula, passport combination, fraud arithmetic) | every push |
| Integration / journey | `backend/tests/test_journey.py` | the real API (httpx ASGI) on **real PostgreSQL and Redis**: `telcron_api_test` built from `db/`, Redis db 1 | every push (`make api-test`) |
| Schema | `db/tests/` | the database's own rules: CHECKs, triggers, `coin_*`, append-only, composite keys; plus `test_performance.py` at volume | every push (`make db-test`), perf on demand (`make db-test-perf`) |
| Drift | `backend/tests/test_schema_drift.py` | models vs. the migrated database: tables, columns, types, nullability, defaults, enum values | every push |
| Contract | `backend/tests/fixtures/<provider>/` (to create) | each provider client against **recorded** responses (SerpApi, ScraperAPI, registries, Bedrock, Rekognition, Textract) | every push, once a client exists |
| AI evaluation | the fixed product set with known recalls and expected labels (WO-004) | the real scorer, on demand | every prompt or model change; a drop in agreement blocks the release |
| Browser | `e2e/` (Playwright): `journey` (local stack), `smoke` (read-only, deployed), `hosted` (live member flow) | `make dev` + demo data, or the dev site | every push (journey in CI; smoke after release) |
| Load | passport reads, live screening, an ingestion run | QA environment | before go-live (tech doc week 9) |
| Acceptance | Telcron's own people, agreed scenarios | QA | before go-live |

## Every change carries these
- **Access**: no token → 401; level or role too low → 403; another user's row → **404**. Each as its own test.
- **Pays once**: anything that earns or spends coins is called twice with the same request and the balance moves
  once. Spend more than the confirmed balance → refused.
- **Append-only**: code never updates `screenings` (beyond completing one), `passports`, `evidence_items`,
  `hazard_*`, `certification_checks`, the ledger or the logs. A change there is a new row; a test asserts the
  version or row count went up.
- **Citations**: a score whose citation is not among the evidence offered becomes `insufficient_data`.
- **The async path**: for an event-driven change, assert the outbox row, then run the handler (tests set
  `RUN_OUTBOX_PUBLISHER=false` and call it directly) and assert its effect.
- **The failure states** the acceptance criteria name: bad input (422), duplicates (409), provider down.

## The revert proof
Before reporting a test, revert the change and watch the test go red, then restore. A test that passes either
way proves nothing; QA will do the same.

## Writing them
- Arrange through the API or the service, as a user would, not by inserting rows that a real flow could never
  produce. Inserting is fine for reference data and for states the API cannot reach yet (say so in a comment).
- One behaviour per test, named as the behaviour: `test_second_review_of_a_product_is_refused`.
- Every test user gets its own email and phone (a verified phone is unique) — use the helpers in the test files.
- Time: never `sleep` to wait for a confirmation. Call what the handler calls (`await rewards.confirm_due(db)`
  in `test_journey.py`), or in a schema test move `confirmable_at`. The browser journey uses a short
  `COIN_CONFIRM_DELAY_SECONDS` instead.
- Browser tests use role and text selectors, wait for state rather than time, and create their own member.
  `smoke` must stay read-only: it runs against the live dev site after every release.

## What not to test
- SQLAlchemy, FastAPI, pydantic or React themselves.
- A mock of the database. The integration tests use the real one; a test that needs PostgreSQL behaviour
  (triggers, CHECKs, locks) belongs in `db/tests/`.
- A real provider. Ever.
- Implementation details (private helpers, exact SQL) unless the detail is the behaviour (an index being used
  is a perf test).

## Reporting
Paste the real summary line: `26 passed in 9.84s`, `13 passed`. A gate that did not run is
`not run — <reason>`. A flaky test is a defect, not a retry.
