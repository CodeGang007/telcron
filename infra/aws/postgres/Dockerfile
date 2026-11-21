# PostgreSQL 18 for the single dev host (ARM64, t4g.small), with every extension the schema creates:
# postgis and vector from the PostgreSQL project's own apt repository (already configured in the
# official image); citext, pg_trgm and btree_gist ship with PostgreSQL.
#
# Not FROM postgis/postgis: that image is published for amd64 only, and this host is arm64.
# db/Dockerfile (local development) stays as it is.
FROM postgres:18

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      "postgresql-${PG_MAJOR}-postgis-3" \
      "postgresql-${PG_MAJOR}-postgis-3-scripts" \
      "postgresql-${PG_MAJOR}-pgvector" \
 && rm -rf /var/lib/apt/lists/*
