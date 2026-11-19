---
name: telcron-module
description: How to build or extend a Telcron backend domain module — the anatomy (router, service, schemas, domain rules, the model mapping, events and handlers), the order to build it in, how modules may talk to each other, and the checklist from work order to DONE-PENDING-QA. Load before creating a module under backend/app/modules, adding a queue handler, or moving logic between layers. For a single endpoint load telcron-api-route instead.
---

# Domain modules

Telcron's backend is one codebase with one module per area of the ERD (tech doc §4.2). Modules today:
`identity`, `catalogue`, `screening`, `community`, `wallet`, `rewards`. Planned: `ingestion`, `media`, `recalls`,
`certifications`, `business` (API keys, webhooks), `admin`. Owners: `telcron-domain-map`.

## Anatomy
```
backend/app/modules/<name>/
  __init__.py
  schemas.py    pydantic request/response models — the contract's shapes
  service.py    the logic; the only public face other modules may call
  router.py     thin HTTP: validate, check level/role, call the service, shape the response
backend/app/domain/<rule>.py     pure functions with exact answers (no I/O), unit-tested
backend/app/models/<domain>.py   the mapping of tables (owned by database-engineer, never created here)
backend/app/workers/handlers/<queue>.py   the Worker side, if the module has slow work
```

### schemas — from the frozen contract
Write the request and response models from `CT-###` first (`tech-lead` freezes it). Field names are the
schema's vocabulary. Responses never include internals (hashes, raw payloads, other users' ids).

### service — where the logic lives
- Takes an `AsyncSession` and plain values; returns models or schemas. No `Request`, no FastAPI imports.
- Orders its writes so the database's rules are satisfied (complete a screening before its passport; insert an
  assessment once, complete). Never works around a trigger, CHECK or `coin_*` function.
- Emits **critical** events with `core.events.emit()` inside the same transaction as the data. A new event type
  needs a route in `ROUTES` (`core/events.py`) and a handler; an unrouted type raises.
- Calls another module only through that module's `service`, never its router, never its tables for writing.

### router — thin
- `APIRouter(tags=["<name>"])`; registered in `backend/app/main.py` **by tech-lead**, under `/api/v1`.
- Dependencies from `core/deps.py`: `Db`, `OptionalUser`, `Level1User`, `require_role(...)`.
- Another user's row is filtered in the `WHERE`, so it is a 404. Every list has a bounded `limit`.
- Error codes are stable `snake_case` strings (`telcron-api-route`), each with a sentence in `frontend/src/lib/api.ts`.

### handler — the Worker side
- One handler per queue; it finishes each event once (`telcron:done:<queue>:<event_id>`) and dead-letters after
  five tries. It opens its own session and commits.
- Outside calls only through a provider client (`telcron-integrations`).

## Build order
1. Read the WO, its contract, `telcron-business-rules` and `telcron-user-flows` for the journey.
2. Ask `database-engineer` for any missing column or table (spec first). Never add a model field yourself.
3. `domain/` rules + their unit tests (exact answers first).
4. `schemas.py` → `service.py` → `router.py`; integration tests through the API (`telcron-testing`).
5. Events and the handler, if any; a test that asserts the outbox row and runs the handler.
6. Report the router export to `tech-lead` for registration; the page to `frontend-engineer` through the contract.

## Checklist
- [ ] Owner and paths match the domain map; no file outside them edited.
- [ ] Schemas match the frozen contract exactly (paths, fields, status codes, level/role).
- [ ] No logic in the router; no FastAPI in the service; pure rules in `domain/`.
- [ ] Reads bounded and indexed (`telcron-performance`); writes satisfy the database rules.
- [ ] Critical events emitted in-transaction and routed; handler idempotent.
- [ ] Access tests (401/403/404), pay-once where coins move, failure states; each goes red on revert.
- [ ] `make api-test` green; `make db-test` green if anything under `db/` changed.
- [ ] WO log has the report with real output; status `DONE-PENDING-QA`.
