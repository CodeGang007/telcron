# Telcron

Consumer product-safety platform — verify a product's identity and safety once, trust it everywhere.

## Local database

Requires Docker and `make` (and [`uv`](https://docs.astral.sh/uv/) for the tests).

```bash
cp .env.example .env     # optional — defaults work out of the box
make db-up               # Postgres 18 + PostGIS + pgvector on localhost:5433
make db-migrate          # create the core schema (38 tables)
make db-seed             # reference data (sources, categories, settings)
make db-sample           # fictional demo products/recalls/passports for building pages
make db-psql             # psql shell        ·  make help for everything else
```

Connection string: `postgresql://telcron:telcron_dev@127.0.0.1:5433/telcron`.
Adminer UI (optional): `docker compose --profile tools up -d adminer` → http://localhost:8080.

## Docs
- Database design, decisions, tests: [`docs/database/schema-design.md`](docs/database/schema-design.md)
- ERD (draw.io, 10 pages): [`docs/database/telcron-erd.drawio`](docs/database/telcron-erd.drawio)
