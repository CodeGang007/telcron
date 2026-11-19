---
name: telcron-infrastructure
description: Telcron's environments and runtime topology — the process model (API, Worker, Redis, PostgreSQL), what runs locally, in CI and on AWS dev today, the target production shape from the technical documentation and the gap between them, settings and environment-variable rules, Docker images, the pull-based release, cost rules and what never to do. Load before changing anything about how Telcron runs, is configured, built or deployed, and before planning QA or production.
---

# Infrastructure

Hands-on commands are in `telcron-dev`; the AWS inventory and operating manual is `docs/runbooks/aws-dev.md`.
This skill is the shape and the rules.

## Process model (ADR-001, ADR-002)
One Python codebase, run as **two services**: the **API** (FastAPI, `uvicorn app.main:app`; also runs the
outbox publisher) and the **Worker** (`python -m app.workers.main`, arq). They meet in **Redis** (queues,
passport cache, rate limits, leaderboard). **PostgreSQL** is the single source of truth. The web app is a static
React build served separately. Nothing else runs.

## Environments
| | Local | CI (`.github/workflows/pipeline.yml`) | AWS dev (live since 2026-11-16) | Target (tech doc §4) |
|---|---|---|---|---|
| API + Worker | `make dev` | full stack for the browser journey | EC2 `t3.micro`, Docker Compose with Caddy (`infra/aws/compose.yml`) | ECS on Fargate, two services |
| Redis | Compose, :6381 | Compose | container on the EC2 host | ElastiCache, multi-AZ |
| PostgreSQL 18 | Compose (`db/Dockerfile`: + PostGIS + pgvector), :5433 | Compose | RDS `db.t4g.micro`, single zone | Aurora PostgreSQL (or RDS if 18 is unavailable — risk 7) |
| Web | Vite :3200 | build only | Lightsail + Caddy | S3 behind CloudFront + WAF |
| Accounts | — | — | one account, `us-east-2` | dev, QA, prod accounts from one Terraform |
| AI | `StubScorer` | stub | Bedrock invoke allowed, quota zero | Nova Pro (dev/QA), Nova Premier locked (prod) |

**The gap is deliberate and unfinished.** Dev runs the cheap shape (about USD 33/month, accepted by the human
on 2026-11-15). QA, production, Terraform, Fargate, Aurora, ElastiCache, CloudFront and WAF are the plan, not the
present. Do not describe them as existing; do not build them without a work order and the human's yes.

## Releases
A push to `main` **is a release to dev**: the pipeline runs schema tests, backend lint and tests, the web build
and the browser journey; on green it commits the web build and a `VERSION` file to `release/dev`; each host's
agent (`infra/aws/agent-*.sh`, systemd timer, once a minute) deploys it; the run then checks the live site
(`e2e/smoke.spec.ts`). Pull-based because the organisation policy forbids GitHub assuming an AWS role and no
access keys are wanted. Never push to `release/dev` by hand. Roll back by reverting on `main`.

## Settings and environment variables
- One file, `.env` (gitignored), serves Compose, `make` and the app; `.env.local` may override. `.env.example`
  lists every key with a safe local default and no secret.
- The app reads settings only through `core/config.py` (pydantic-settings). A new setting gets a typed field
  there, a line in `.env.example`, and — if it is secret — a field in the `telcron/dev/app` secret, written by
  `deploy-host.sh`.
- `ENV` is `local`, `test` or `dev` (later `qa`, `prod`). The app refuses the default `JWT_SECRET` outside
  local/test. `DEV_EXPOSE_CODES` and `SEED_ADMIN_PASSWORD` are local/dev conveniences; never in production.
- Secrets live in Secrets Manager on AWS and are read by the instance role. Never print, log or commit one.

## Images
- `backend/Dockerfile` builds the one image both services run (different commands). CI builds it on every push.
- `db/Dockerfile` is PostgreSQL 18 + PostGIS + pgvector for local and CI. RDS provides its own extensions.
- Pin base images to a major version; rebuild, do not patch running containers.

## Cost and change rules
- Anything that **adds cost** or **deletes** a resource needs the human's explicit yes first, with the monthly
  figure. The account is on the free plan with a fixed credit; the budget alarm is USD 22.
- Every created, changed or removed resource is recorded in `docs/runbooks/aws-dev.md` in the same change.
  Identifiers go only in the gitignored `aws-dev.local.md`.

## Never
- Open 5432 to the internet, or 22 on the EC2 host (Session Manager only).
- Create access keys, or an identity provider for GitHub.
- Run a migration against the RDS database by hand without the human's yes — the release does it.
- Put a hostname, IP, account id or resource id in a tracked file. The repository is public.
- Kill local servers by name: other projects run on the same machines. Use `make dev-stop`.
