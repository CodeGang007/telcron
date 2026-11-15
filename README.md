# Telcron

Consumer product-safety platform — verify a product's identity and safety once, trust it everywhere.

Scan or search a product and read its **passport**: recalls, certificates and seven hazard scores,
each with the evidence behind it. Verified members add reviews and hazard flags and earn TelCoins.

## What is here

| Path | What |
| --- | --- |
| `backend/` | FastAPI. One codebase, two services: the API and an arq Worker fed by a transactional outbox |
| `frontend/` | React + Vite + Tailwind web app |
| `.claude/` | Agents and skills this project is built with |
| `docs/agent-workspace/` | Board, work orders, defects, worklog |
| `docs/decisions/` | Decision records |
| `docs/runbooks/` | Local development and the AWS dev environment |

The database design (PostgreSQL 18, 90 tables in 14 domains) lives on branch
[`feat/database-schema`](../../tree/feat/database-schema). The backend here carries a provisional copy
of that schema; bringing the two together is the first open work order (WO-011).

## Run it locally

Requires Docker, [`uv`](https://docs.astral.sh/uv/) and Node 22 or later.

```bash
docker compose up -d postgres redis      # PostgreSQL 18 + pgvector on :5436, Redis on :6381
cp .env.example .env.local               # set JWT_SECRET to `openssl rand -hex 32`
cd backend && uv sync && uv run alembic upgrade head && uv run python -m app.seed && cd ..
cd frontend && npm install && cd ..
tools/dev-all.sh                         # API :4310, Worker, web :3200
```

Open http://localhost:3200. API documentation is at http://localhost:4310/docs. The seed loads three
invented demo products; one of them is recalled.

## What works today

- Sign-up with an email and a phone code, sign-in, rotating sessions, lockout
- Product search by name, brand or barcode, and the passport page with its evidence
- Reviews and hazard flags from verified members; a review triggers a re-screen and a new passport version
- Digital Wallet, with an alert when a saved product's passport changes
- TelCoins: pending then confirmed, a daily cap, fraud holds, levels, a monthly leaderboard

## What does not, yet

- **Hazard scores come from a keyword placeholder, not an AI model.** Amazon Bedrock is not wired.
- Verification codes are shown on screen locally; nothing is emailed or texted.
- No scraping or ingestion, no photo upload, no Level 2 identity check, no business API.
- Nothing is deployed. The AWS hosts exist and are empty.

The full list, with owners, is `docs/agent-workspace/BOARD.md`.

## Tests

```bash
cd backend && uv run ruff check . && uv run pytest -q
cd frontend && npx tsc --noEmit && npm run build
```
