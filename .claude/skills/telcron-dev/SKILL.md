---
name: telcron-dev
description: How to run Telcron locally and reach the AWS dev environment — Docker services, migrations, seeds, the three processes, tests, ports, local sign-ins and common failures. Load at the start of any hands-on session.
---

# Running Telcron

```bash
cp .env.example .env        # first time; set JWT_SECRET to `openssl rand -hex 32`
make app-db                 # Postgres + Redis up; migrate; reference data; phases 2-3; demo data; app seed
cd frontend && npm install && cd ..
make dev                    # API :4310, Worker, web :3200 — detached, logs in .dev-logs/
make dev-stop
```

`make help` lists every target. One process at a time instead:
`cd backend && uv run uvicorn app.main:app --port 4310 --reload`,
`cd backend && uv run python -m app.workers.main`, `cd frontend && npm run dev`.

**Always run the Worker for real testing.** A review is HTTP → outbox → publisher (inside the API) → Redis →
Worker → new passport. Without the Worker nothing is re-screened and no coin is ever confirmed.

- One settings file, `.env`, serves Docker Compose, `make` and the application. `.env.local` may override it.
- Ports: Postgres :5433 by default (`DB_PORT`), Redis :6381, API :4310, web :3200. If 5433 is taken on your
  machine, set `DB_PORT` and `DATABASE_URL` in `.env`.
- API docs: http://localhost:4310/docs · health: http://localhost:4310/health
- Demo data is the database's (`make db-sample`): four FICTIONAL products, one per passport state:
  `acme-powerblend-1000` (recalled), `northwind-chillmate-31` (verified), `contoso-fastcharge-65w`
  (certificate issue), `unidentified-desk-lamp` (needs information). Its accounts have no password.
- Local admin: `admin@telcron.example.com`, created by `uv run python -m app.seed` only when
  `SEED_ADMIN_PASSWORD` is set in `.env`.
- With `DEV_EXPOSE_CODES=true` the sign-up screen shows the two codes; nothing is emailed or texted.
- `COIN_CONFIRM_DELAY_SECONDS=15` makes the app seed shorten the earn rules' confirmation delay locally.
- Start and stop with `make dev` / `make dev-stop` only. Never kill dev servers by name: other projects'
  servers run on the same machines.

## Gates
```bash
make api-test     # ruff + pytest; the tests build their own database from db/
make db-test      # the schema's own suite, on a throwaway Postgres
cd frontend && npx tsc --noEmit && npm run build
cd e2e && npm run journey     # the member's journey in a browser; needs `make dev` and the demo data
```

The journey creates a new member on every run. It needs `DEV_EXPOSE_CODES=true` and a short
`COIN_CONFIRM_DELAY_SECONDS`. `npm run smoke` is the read-only set for a deployed site
(`BASE_URL`, `API_URL`, optional `EXPECT_VERSION`).

## Releases
A push to `main` runs the pipeline and, when it is green, deploys to AWS dev by itself: the workflow
commits the web build and a `VERSION` file to `release/dev`, and each host's agent deploys it within
about a minute (the backend host builds the image first, a few minutes). `/health` on the API and
`/version.txt` on the web host name the commit that is live.

## When something is off
- Passport did not change after a review: is the Worker running? `tail .dev-logs/worker.log`.
- Stale passport: `docker compose exec redis redis-cli del telcron:passport:<product_id>`.
- Failed jobs: `docker compose exec redis redis-cli lrange telcron:dead-letter 0 -1`.
- `relation "hazard_assessments" does not exist`: phases 2-3 are missing. `make db-next`.
- Start clean: `make db-reset`, then `make db-next` and `cd backend && uv run python -m app.seed`.

AWS dev is described in `docs/runbooks/aws-dev.md`: what runs where, how to look at it, how to sign in.
