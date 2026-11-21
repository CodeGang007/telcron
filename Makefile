SHELL := /bin/bash
COMPOSE := docker compose
-include .env
export

PSQL := $(COMPOSE) exec -T db psql -U $${POSTGRES_USER:-telcron} -d $${POSTGRES_DB:-telcron} -v ON_ERROR_STOP=1 -q
PYTEST := uv run -q --no-project --with 'psycopg[binary]>=3.2' --with 'pytest>=8' pytest

.PHONY: help db-up db-down db-migrate db-rollback db-status db-seed db-sample db-reset db-psql db-nuke \
        db-test db-test-perf db-gen db-erd-png up db-next app-db api-test eval eval-research eval-assistant embedder dev dev-stop

help:  ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

db-up:  ## start Postgres (build image on first run)
	$(COMPOSE) up -d --build --wait db

db-down:  ## stop Postgres (data is kept)
	$(COMPOSE) down

db-migrate: db-up  ## apply pending migrations
	$(COMPOSE) run --rm migrate up

db-rollback:  ## roll back the latest migration
	$(COMPOSE) run --rm migrate rollback

db-status:  ## show migration status
	$(COMPOSE) run --rm migrate status

db-seed:  ## load reference data (idempotent)
	@for f in db/seeds/0*_*.sql; do echo "seeding $$f"; $(PSQL) < $$f; done

db-sample:  ## load demo data for building pages (idempotent)
	$(PSQL) < db/seeds/dev/sample_data.sql

db-reset:  ## wipe the local database, re-migrate, seed + demo data
	$(COMPOSE) exec -T db psql -U $${POSTGRES_USER:-telcron} -d postgres -q -c "DROP DATABASE IF EXISTS $${POSTGRES_DB:-telcron} WITH (FORCE)" -c "CREATE DATABASE $${POSTGRES_DB:-telcron}"
	$(MAKE) db-migrate db-seed db-sample

db-psql:  ## open a psql shell
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-telcron} -d $${POSTGRES_DB:-telcron}

db-nuke:  ## stop and DELETE the data volume
	$(COMPOSE) down -v

db-test:  ## run the schema test suite on a throwaway in-memory Postgres
	$(COMPOSE) build -q db   # db-test reuses this image; on a fresh machine it does not exist yet
	$(COMPOSE) --profile test up -d --wait db-test
	TELCRON_TEST_ADMIN_DSN=postgresql://postgres:test@127.0.0.1:$${DB_TEST_PORT:-55433}/postgres \
	  $(PYTEST) db/tests --ignore=db/tests/test_performance.py -q; s=$$?; \
	  $(COMPOSE) --profile test stop db-test >/dev/null; exit $$s

db-test-perf:  ## run read-path performance tests (~1 min, loads ~1M rows)
	$(COMPOSE) build -q db
	$(COMPOSE) --profile test up -d --wait db-test
	TELCRON_TEST_ADMIN_DSN=postgresql://postgres:test@127.0.0.1:$${DB_TEST_PORT:-55433}/postgres \
	  $(PYTEST) db/tests/test_performance.py -q -s; s=$$?; \
	  $(COMPOSE) --profile test stop db-test >/dev/null; exit $$s

db-gen:  ## regenerate SQL + ERD + catalogue from docs/database/schema_spec.py
	python3 docs/database/schema_spec.py
	python3 docs/database/tools/build_sql.py
	python3 docs/database/tools/build_erd.py

# ───────────────────────── application (backend/ + frontend/) ─────────────────────────
up:  ## start Postgres and Redis
	$(COMPOSE) up -d --build --wait db redis

db-next:  ## apply phases 2-3 from db/schema-next to the LOCAL database (the backend needs them; skipped if present)
	@if [ "$$($(PSQL) -Atc "select to_regclass('hazard_assessments') is not null")" = "t" ]; then \
	  echo "phases 2-3 already applied"; \
	else \
	  for f in phase2_schema phase2_rules phase3_schema phase3_rules seed_reference; do \
	    echo "applying db/schema-next/$$f.sql"; $(PSQL) -1 < db/schema-next/$$f.sql || exit 1; done; \
	fi

app-db: up  ## everything the backend needs in the local database: migrate, reference data, phases 2-3, demo data
	$(MAKE) db-migrate db-seed db-next db-sample
	cd backend && uv run python -m app.seed

eval:  ## grade the configured hazard scorer against backend/evals/cases.json
	cd backend && uv run python -m evals.run

eval-assistant:  ## grade the product assistant against backend/evals/assistant_cases.json (needs LLM_API_KEY)
	cd backend && uv run python -m evals.assistant

embedder:  ## run the embedding model locally on :4320 (set EMBED_URL=http://localhost:4320 in .env)
	cd services/embedder && uv run --python 3.12 --with-requirements requirements.txt \
	  env EMBED_CACHE=$(CURDIR)/.models uvicorn app:app --port 4320

eval-research:  ## grade the research reader against backend/evals/research_cases.json (needs LLM_API_KEY)
	cd backend && uv run python -m evals.research

api-test:  ## backend lint and tests (the tests build their own database from db/ inside the local Postgres)
	cd backend && uv run ruff check . && uv run pytest -q

dev:  ## start the API (:4310), the Worker and the web app (:3200), detached; logs in .dev-logs/
	tools/dev-all.sh

dev-stop:  ## stop them
	tools/dev-all.sh stop

db-erd-png:  ## export ERD pages to docs/database/preview/*.png (needs draw.io desktop)
	@mkdir -p docs/database/preview
	@for i in $$(seq 1 10); do drawio -x -f png -p $$i -b 10 -o docs/database/preview/page-$$i.png docs/database/telcron-erd.drawio >/dev/null 2>&1; done
