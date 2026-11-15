"""The Worker service: one arq worker per job queue, in one process.

Wired: screening, coins, alerts. NOT wired (no consumer runs, by design — a queue with a
placeholder consumer would swallow jobs): ingest (WO-003), media and identity (WO-004).
"""

import asyncio
import json
import logging
import signal
from datetime import UTC, datetime
from typing import Any

from arq import Retry
from arq.worker import Worker, func

from app.core.events import DEAD_LETTER_KEY, ROUTES, queue_name
from app.core.redis import redis_settings
from app.workers.handlers import alerts, coins, screening

log = logging.getLogger("telcron.worker")
HANDLERS = {"screening": screening.handle, "coins": coins.handle, "alerts": alerts.handle}
MAX_TRIES = 5
DONE_TTL = 7 * 24 * 3600


async def handle(ctx: dict[str, Any], event_id: str, event_type: str,
                 payload: dict[str, Any]) -> str:
    queue = ROUTES[event_type]
    redis = ctx["redis"]
    done_key = f"telcron:done:{queue}:{event_id}"
    # A job delivered twice does its work once.
    if await redis.exists(done_key):
        return "duplicate"
    try:
        await HANDLERS[queue](event_type, payload)
    except Exception as exc:
        if ctx["job_try"] >= MAX_TRIES:
            await redis.rpush(DEAD_LETTER_KEY, json.dumps({
                "event_id": event_id, "event_type": event_type, "payload": payload,
                "queue": queue, "error": repr(exc), "failed_at": datetime.now(UTC).isoformat()}))
            log.error("dead-lettered %s %s: %r", event_type, event_id, exc)
            return "dead-letter"
        raise Retry(defer=min(300, 5 * 2 ** ctx["job_try"])) from exc
    await redis.set(done_key, "1", ex=DONE_TTL)
    return "ok"


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    workers = [Worker(functions=[func(handle, name="handle", max_tries=MAX_TRIES)],
                      queue_name=queue_name(q), redis_settings=redis_settings(),
                      handle_signals=False, max_jobs=10, poll_delay=0.5, keep_result=3600)
               for q in HANDLERS]
    tasks = [asyncio.create_task(w.async_run()) for w in workers]
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker up: %s", ", ".join(HANDLERS))
    await stop.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for w in workers:
        await w.close()


if __name__ == "__main__":
    asyncio.run(main())
