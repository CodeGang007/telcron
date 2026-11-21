# ADR-007: The dev environment runs on one host, database included

Date: 2026-11-21 · Status: accepted (by the human, in chat)

## Context
Dev ran on an EC2 `t3.micro` (Caddy, API, Worker, Redis) and RDS `db.t4g.micro` (PostgreSQL 18), about
USD 33 a month against a fixed credit. RDS alone was about 14 of that. The application also needs a
place for the new embedding service (an open model on the CPU, about 500 MB of memory), which does not
fit beside the stack in the `t3.micro`'s 1 GB.

## Decision
One EC2 `t4g.small` (arm64, 2 GB, Amazon Linux 2023) runs everything in Docker Compose
(`infra/aws/compose.yml`): Caddy, API, Worker, Redis, PostgreSQL 18 with postgis, vector, citext,
pg_trgm and btree_gist, and the embedder. The web front end stays on Lightsail. The data moves from RDS
once (`infra/aws/migrate-from-rds.sh`, which compares row counts and object counts on both sides); then
RDS and the `t3.micro` are deleted. The host costs about USD 17.50 a month, the environment about 23.

- PostgreSQL is built from the official `postgres:18` image plus the PostgreSQL project's postgis and
  pgvector packages (`infra/aws/postgres/Dockerfile`); `postgis/postgis` is published for amd64 only.
- The application's role `telcron_app` owns the schema and is no longer a (RDS) superuser. The
  `postgres` superuser, whose password is `PG_SUPERUSER_PASSWORD` in the app secret, creates the
  extensions. Nothing is published beyond Caddy's 80 and 443.
- Backups: `pg_dump` every night at 02:30 UTC to the private raw bucket, kept 14 days
  (`infra/aws/backup-db.sh`); restore with `infra/aws/restore-db.sh`.

## Consequences
- No managed backups, point-in-time recovery, failover or minor-version patching. Up to a day of data
  can be lost; a lost disk means restoring last night's dump onto a new host.
- One host is a single point of failure, and deploy-time image builds share its 2 GB (with 2 GB swap).
- The database's tuning and upgrades are ours (`shared_buffers` 128 MB, 40 connections).
- To move back to RDS (for production, or when dev needs more): create the RDS instance, let its master
  user create the extensions and `telcron_app`, restore the newest dump with the same filtered
  `pg_restore --role=telcron_app --no-owner --no-privileges` as `db-lib.sh` `load_dump`, point
  `DATABASE_URL` at it with `?ssl=require` in `deploy-host.sh`, and drop the `postgres` service and the
  migrate step's local target from compose. The git history before this ADR has the RDS version of
  `deploy-host.sh`.
