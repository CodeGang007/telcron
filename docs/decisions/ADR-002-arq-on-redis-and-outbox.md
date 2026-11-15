# ADR-002 — arq on Redis for queues, with a transactional outbox

Date: 2026-11-15 · Status: accepted

The technical documentation calls for Redis job queues fed by an outbox. arq is a small asyncio-native job library on Redis that fits FastAPI's async code. Critical events are written to `outbox_events` in the same transaction as their data; a publisher inside the API service moves them to one arq queue per job type. Handlers are idempotent through a Redis key per finished event, and dead-letter after five tries. If volume or other teams ever need the events, the queue sits behind `core/events.py` and `workers/` and can move to SQS.
