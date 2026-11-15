# Telcron

Consumer product-safety platform — verify a product's identity and safety once, trust it everywhere.

Scan or search a product and read its **passport**: recalls, certificates and seven hazard scores,
each with the evidence behind it. Verified members add reviews and hazard flags and earn TelCoins.

## What is here

| Path | What |
| --- | --- |
| `db/`, `docs/database/` | The database: PostgreSQL 18, 90 tables in 14 domains, generated from `schema_spec.py` |
| `backend/` | FastAPI. One codebase, two services: the API and an arq Worker fed by a transactional outbox |
| `frontend/` | React + Vite + Tailwind web app |
| `.claude/` | Agents and skills this project is built with |
| `docs/agent-workspace/` | Board, work orders, defects, worklog |
| `docs/decisions/`, `docs/runbooks/` | Decision records; local development and the AWS dev environment |

## Run it locally

Requires Docker, `make`, [`uv`](https://docs.astral.sh/uv/) and Node 22 or later.

```bash
cp .env.example .env     # set JWT_SECRET to `openssl rand -hex 32`
make app-db              # Postgres 18 + PostGIS + pgvector and Redis; migrations, reference data,
                         # phases 2-3, fictional demo products
cd frontend && npm install && cd ..
make dev                 # API :4310, Worker, web :3200   ·   make dev-stop
```

Open http://localhost:3200. API documentation is at http://localhost:4310/docs.

Database only: `make db-up db-migrate db-seed db-sample`, then `make db-psql`.
Connection string: `postgresql://telcron:telcron_dev@127.0.0.1:5433/telcron`.
Adminer UI (optional): `docker compose --profile tools up -d adminer` → http://localhost:8080.

## What works today

- Sign-up with an email and a phone code, sign-in, rotating sessions, lockout
- Product search by name, brand or barcode, and the passport page with its evidence
- Reviews and hazard flags from verified members; a review triggers a re-screen and a new passport version
- Digital Wallet, with an alert when a saved product is recalled or its certificate fails
- TelCoins through the database's own functions: pending then confirmed, daily cap, fraud holds, levels

## What does not, yet

- **Hazard scores come from a keyword placeholder, not an AI model.** Amazon Bedrock is not wired.
- Verification codes are shown on screen locally; nothing is emailed or texted.
- No scraping or ingestion, no photo upload, no Level 2 identity check, no business API.
- Nothing is deployed. The AWS hosts exist and are empty.

The full list, with owners, is `docs/agent-workspace/BOARD.md`.

## Tests

```bash
make db-test      # the schema's own suite, on a throwaway Postgres
make api-test     # backend lint and tests, on a database built only from db/
cd frontend && npx tsc --noEmit && npm run build
```

## Docs
- Database design, decisions, tests: [`docs/database/schema-design.md`](docs/database/schema-design.md)
- ERD (draw.io, 10 pages): [`docs/database/telcron-erd.drawio`](docs/database/telcron-erd.drawio)
- How the application is built and run: [`CLAUDE.md`](CLAUDE.md)
