---
name: telcron-architecture
description: How Telcron is put together — the API and Worker services, the outbox, the six queues, the module layout and the rules the code follows. Load before designing a feature, adding a module, a queue, an event or a handler, or reviewing whether a change fits.
---

# Architecture

One Python codebase, two services. The **API** (`app/main.py`, FastAPI) answers requests and writes events.
The **Worker** (`app/workers/main.py`, arq) does everything slow and is the only part that calls outside
sources. They talk through Redis queues. **PostgreSQL is the single source of truth.**

```
backend/app/
  core/      config, db session, security, auth dependencies, the outbox (events.py), redis
  domain/    pure rules with exact answers: hazard formula, passport combination, coin fraud rules
  models/    a mapping of the 90 tables in db/ (never creates them), one file per domain
  modules/<name>/  router.py (HTTP), service.py (logic), schemas.py (pydantic)
  workers/   publisher.py (outbox -> queues), main.py (consumers), handlers/<queue>.py
frontend/src/  lib (api client, auth), components, pages
```

## Events
- A **critical** event is written with `core.events.emit()` in the same transaction as the data it describes.
  The publisher inside the API moves it to Redis. If Redis is down it waits in `outbox_events`.
- `ROUTES` in `core/events.py` maps an event type to a queue. An unrouted type raises at `emit()`.
- Queues: `ingest`, `media`, `screening`, `identity`, `coins`, `alerts`, plus the dead-letter list.
  Wired today: `screening`, `coins`, `alerts`. A queue with no real consumer has no worker at all.
- A handler finishes each event once (`telcron:done:<queue>:<event_id>`) and dead-letters after five tries.

## Rules
- Routers are thin: validate, call the service, shape the response. Logic lives in `service.py`; rules with an
  exact answer live in `domain/` as pure functions with unit tests.
- A module imports another module's `service`, never its router, and never reaches into its tables to write.
- The database's rules are the rules (`db/**/*_rules.sql`): append-only history, the `coin_*` functions,
  screening and passport triggers, risk fan-out. Services order their writes to satisfy them.
- A passport is never edited: a re-screen issues a new version.
- Reference data and user data are kept apart from derived data (screenings, passports, risk events), which can
  always be rebuilt.
- A provider client is the only file that talks to its provider.
- Departures from the v2 architecture document are recorded in `docs/decisions/`.
