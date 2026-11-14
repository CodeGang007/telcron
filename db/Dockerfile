# PostgreSQL 18 + PostGIS 3.6 (official image) + pgvector. citext, pg_trgm, btree_gist ship with Postgres.
FROM postgis/postgis:18-3.6

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-18-pgvector \
 && rm -rf /var/lib/apt/lists/*
