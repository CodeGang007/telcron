---
name: telcron-dev
description: How to run Telcron locally and reach the AWS dev environment — Docker services, migrations, seed, the three processes, tests, ports, local sign-ins and common failures. Load at the start of any hands-on session.
---

# Running Telcron

```bash
docker compose up -d postgres redis      # Postgres 18 + pgvector on :5436, Redis on :6381
cp .env.example .env.local               # first time only; set JWT_SECRET to `openssl rand -hex 32`
cd backend && uv sync && uv run alembic upgrade head && uv run python -m app.seed && cd ..
cd frontend && npm install && cd ..
tools/dev-all.sh                         # API :4310, Worker, web :3200 — detached, logs in .dev-logs/
tools/dev-all.sh stop
```
One at a time instead: `cd backend && uv run uvicorn app.main:app --port 4310 --reload`,
`cd backend && uv run python -m app.workers.main`, `cd frontend && npm run dev`.

**Always run the Worker for real testing.** A review is HTTP → outbox → publisher (inside the API) → Redis →
Worker → new passport. Without the Worker nothing is re-screened and no coin is ever confirmed.

- API docs: http://localhost:4310/docs · health: http://localhost:4310/health
- Local admin: `admin@telcron.example.com`, created by the seed only when `SEED_ADMIN_PASSWORD` is set in `.env.local`.
- Demo products are invented: `aquablend-900`, `voltpro-65w-charger`, `brightbuild-magnet-set` (recalled).
- With `DEV_EXPOSE_CODES=true` the sign-up screen shows the two codes; nothing is emailed or texted.
- `COIN_CONFIRM_DELAY_SECONDS=15` in `.env.local` confirms coins after 15 seconds instead of 10 minutes.
- Ports are offset on purpose: Osten's stack uses :5434 and :6379 on this machine.

## Gates
```bash
cd backend && uv run ruff check . && uv run pytest -q
cd frontend && npx tsc --noEmit && npm run build
```

## When something is off
- Passport did not change after a review: is the Worker running? `tail .dev-logs/worker.log`.
- Stale passport: `docker compose exec redis redis-cli del telcron:passport:<product_id>`.
- Failed jobs: `docker compose exec redis redis-cli lrange telcron:dead-letter 0 -1`.
- Start clean: `docker compose down -v`, then the setup block again.

AWS dev is described in `docs/runbooks/aws-dev.md`. Nothing is deployed there yet.
