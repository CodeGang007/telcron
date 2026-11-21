# AWS dev environment

Region `<region>`. The repository is public, so the region, the app secret's name (`<app secret>`), the
account id, resource ids, IP addresses, hostnames and the database endpoint are **not** in this file. They are in the console, in the repository's Actions
variables (`DEV_WEB_URL`, `DEV_API_URL`) and in `docs/runbooks/aws-dev.local.md`, which is gitignored.

The dev site has been live since 2026-11-16. Nobody holds AWS access keys: people use the console or
`aws login`; the EC2 host uses its instance role; GitHub holds no AWS credentials at all.

**One host since 2026-11-21 (ADR-007).** RDS and the `t3.micro` were replaced by one
`t4g.small` that also runs PostgreSQL and the embedder. The cutover below was done on 2026-11-21: data
identical (111 tables, 1,214 rows), about three minutes of downtime; the old pair was then deleted.

## What runs where

| Where | What |
| --- | --- |
| EC2 `telcron-dev-host` (`t4g.small`, arm64, 2 GB, Amazon Linux 2023) | Docker Compose: Caddy (HTTPS), API, Worker, Redis, PostgreSQL 18 (postgis, vector, citext, pg_trgm, btree_gist), embedder. `infra/aws/compose.yml` |
| Lightsail `telcron-dev-web` (Debian 12, smallest bundle) | Caddy serving the built web app from `/var/www/telcron` |
| *Deleted 2026-11-21 after the cutover:* EC2 `telcron-dev-backend` (`t3.micro`) and RDS `telcron-dev` | Final RDS dump kept in the raw bucket under `backups/rds-final/` |

Both public hosts have a fixed address and a hostname that encodes it (a wildcard-DNS service), with
Let's Encrypt certificates that Caddy obtains and renews. A real domain would replace both. The API's
Elastic IP moves from the old instance to the new one, so the API hostname does not change.

Only Caddy publishes ports (80, 443). PostgreSQL, Redis and the embedder are reachable only on the
compose network. The application logs in as `telcron_app`, which owns the schema and is not a
superuser; the `postgres` superuser creates the extensions. Memory plan for 2 GB plus 2 GB swap:
PostgreSQL about 300 MB (capped at 600 MB; `shared_buffers` 128 MB, 40 connections), embedder about
500 MB (capped at 700 MB), API 150 MB, Worker 100 MB, Redis 96 MB, Caddy 30 MB.

The compose network is `app`, a fixed private range declared in `infra/aws/compose.yml`, with Caddy on a
fixed address in it. The API believes X-Forwarded-For only from that address (`TRUSTED_PROXIES`, set in
the same file), so per-IP rate limits count each visitor, not Caddy. Caddy discards any X-Forwarded-For
the visitor sent and writes the real one (its default with no `trusted_proxies`); uvicorn's own
proxy-header handling is off (`backend/Dockerfile`). If Caddy's address or the range changes, change
`TRUSTED_PROXIES` with it. The first release after this change creates the network and leaves the old,
empty `telcron-app_default` behind; `docker network rm telcron-app_default` removes it (no cost either way).

## How a release happens

1. A push to `main` runs `.github/workflows/pipeline.yml`: a dependency scan (`tools/dependency-scan.sh`:
   `backend/uv.lock` with pip-audit, `frontend/` and `e2e/` lockfiles with `npm audit`; any High or
   Critical advisory, or a scan that cannot rate a finding, fails the run), schema tests, backend lint
   and tests, web typecheck and build, and the member's journey in a browser against a full stack.
   The advisories are live data, so a new High advisory can stop releases without any code change: the
   owner of that lockfile bumps the package, and nothing is released until they do.
2. If all of it passes, the `release` job builds the web app, and commits it with a `VERSION` file naming
   the commit to the `release/dev` branch. That is the whole release: a commit on a branch.
3. Each host runs a small agent from a systemd timer, once a minute. It asks GitHub where `release/dev`
   points. When that has moved:
   - the EC2 host (`infra/aws/agent-backend.sh` → `deploy-host.sh`) checks out the commit, builds the
     backend image, builds the PostgreSQL and embedder images (cached), starts PostgreSQL and Redis,
     updates the database roles and extensions, runs the migrations (dbmate, phases 1-3), loads reference data,
     restarts the stack and seeds the admin;
   - the Lightsail host (`infra/aws/agent-web.sh`) copies the new web build into place.
4. The `release` job waits until the API's `/health` and the web host's `/version.txt` both report the
   new commit, then runs read-only checks against the live site (`e2e/smoke.spec.ts`).

A release that fails to deploy on the EC2 host is retried every ten minutes, and the pipeline run fails
after twenty. Nothing is rolled back automatically: the previous containers keep running until the new
ones are up. To roll back, revert the commit on `main`.

Why pull-based: the account's organisation policy denies creating the identity provider that would let
GitHub assume a role, and long-lived access keys in GitHub were not wanted. The hosts therefore fetch
their releases, and anyone who can write to `release/dev` can deploy to dev. Protect that branch.

## Looking at it

```bash
aws login                                   # your own sign-in; region <region>
# what the backend host's agent did last
aws ssm send-command --document-name AWS-RunShellScript --instance-ids <instance id> \
  --parameters 'commands=["journalctl -u telcron-deploy -n 60 --no-pager"]'
aws ssm get-command-invocation --command-id <id> --instance-id <instance id> --query StandardOutputContent --output text
# on the host:
#   docker compose -f /opt/telcron/repo/infra/aws/compose.yml --env-file /opt/telcron/.env ps
#   journalctl -u telcron-backup -n 30 --no-pager          # last night's backup
#   docker compose ... exec postgres psql -U postgres -d telcron   # a SQL shell (local socket)
```

The EC2 host is reached through Session Manager; it has no SSH key and port 22 is closed. The Lightsail
host is reached with the account's Lightsail key over SSH; its agent logs to `journalctl -u telcron-web-deploy`.

To deploy by hand, run `infra/aws/deploy-host.sh` on the EC2 host with the variables its header lists.
To set a host up again from nothing: `infra/aws/setup-backend-host.sh` (also usable as EC2 user-data,
see its header), `infra/aws/setup-web-host.sh`.

## Backups and restore

`telcron-backup.timer` runs `infra/aws/backup-db.sh` every night at 02:30 UTC: `pg_dump` in custom
format (compressed) to `s3://telcron-dev-raw-<account-id>/backups/postgres/YYYY/MM/DD.dump`, checked by
listing it back, then every object under that prefix older than 14 days is deleted. The host role's
existing S3 permissions on the raw bucket cover it. Run it by hand with
`bash /opt/telcron/repo/infra/aws/backup-db.sh`.

To restore (destructive: everything written since that backup is lost):

```bash
# on the host, through Session Manager; newest backup unless DUMP_KEY (or DUMP_FILE) is given
CONFIRM=replace-the-database DUMP_KEY=backups/postgres/2026/12/01.dump \
  bash /opt/telcron/repo/infra/aws/restore-db.sh
```

It stops the API and Worker, drops and recreates the database owned by `telcron_app`, lets the
superuser create the extensions, restores everything else as `telcron_app` in one transaction, then
runs `deploy-host.sh` for the checked-out commit (newer migrations, reference data) and
starts the stack. The dump made at the cutover is kept separately under `backups/rds-final/` and is
not touched by the 14-day clean-up.

If the instance or its disk is lost: launch a new host with the setup script, wait for its first
deploy, then run `restore-db.sh` with the newest backup. Data since 02:30 UTC that night is lost.

## Cutover from RDS (one time, ADR-007)

Every step that creates, changes or deletes something needs the human's yes (given for this plan on
2026-11-21). Values in angle brackets are in `aws-dev.local.md` or the console.

1. Add `PG_SUPERUSER_PASSWORD` (for example 64 hex characters) to the `<app secret>` secret, keeping
   its other fields. Never print the secret.
2. On the old host: `systemctl disable --now telcron-deploy.timer`, so it keeps running its current
   release untouched (the new `deploy-host.sh` would refuse there anyway).
3. Push `main`. The pipeline publishes the release; its live-site check cannot pass until the cutover
   is done (re-run the `release` job afterwards).
4. Launch `telcron-dev-host`: AMI from the SSM parameter
   `/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64`, `t4g.small`, the old
   instance's subnet, security group `telcron-dev-backend`, instance profile `telcron-dev-backend`,
   20 GB gp3 encrypted root volume, IMDSv2 required with hop limit 2 (the containers use the role),
   no key pair, a public IPv4 address for now, tags `project=telcron`, `env=dev`, user-data as in
   `setup-backend-host.sh`'s header. Its first deploy takes several minutes (image builds).
5. On the old host: `docker compose ... stop api worker` (no more writes to RDS).
6. On the new host: `OLD_DB_HOST=<rds endpoint> bash /opt/telcron/repo/infra/aws/migrate-from-rds.sh`.
   It prints every table's row count on both sides and stops on any difference.
7. Move the Elastic IP `telcron-dev-backend` to the new instance (allow reassociation). Then on the
   new host `docker compose ... restart caddy` so it obtains the certificate at once.
8. Check: `/health` names the release commit, the web app signs in, `backup-db.sh` run once by hand
   writes an object to S3. Re-run the pipeline's `release` job.
9. With the human's yes: delete the old instance, then RDS (turn off deletion protection first; the
   dump under `backups/rds-final/` is the copy, a final snapshot is optional and costs storage), the
   `telcron-dev-db` security group, and the role's RDS-master-secret permission. Update this file and
   `aws-dev.local.md`.

Keys for outside services (Groq, Gemini, Tavily, Gmail): `docs/runbooks/api-keys.md`.

## Signing in to the dev site

Sign-up is closed there: the application cannot send verification codes yet (WO-005), and codes are never
shown on a deployed build. One admin exists, `admin@telcron.example.com`; its password is the
`SEED_ADMIN_PASSWORD` field of the `<app secret>` secret. The demo products are fictional.

## What exists

| Resource | Name | Notes |
| --- | --- | --- |
| EC2 instance | `telcron-dev-host` | `t4g.small` arm64, Amazon Linux 2023, 20 GB gp3 encrypted, IMDSv2 only (hop limit 2), no key pair, 2 GB swap. Id `<instance id>` in `aws-dev.local.md`. Created at the cutover |
| Elastic IP | `telcron-dev-backend` | Attached to `telcron-dev-host` after the cutover (until then, to the old instance) |
| EC2 instance (old) | `telcron-dev-backend` | `t3.micro`. **Terminated 2026-11-21** after the cutover |
| Lightsail instance, static IP | `telcron-dev-web`, `telcron-dev-web-ip` | The blueprint's own stack (nginx, MariaDB, PHP, phpMyAdmin, Varnish) is stopped and disabled |
| RDS PostgreSQL (old) | `telcron-dev` | **Deleted 2026-11-21** (no final snapshot; the final dump is in the raw bucket under `backups/rds-final/`) |
| Security group | `telcron-dev-backend` | 80 and 443 in. (`telcron-dev-db` deleted with RDS) |
| IAM role and instance profile | `telcron-dev-backend` | Session Manager, ECR read, the two buckets, the secrets under the app secret's prefix (`<app secret prefix>/*`), Bedrock invoke, SES send (`telcron-dev-ses-send`), Rekognition DetectText/DetectLabels (`telcron-dev-rekognition`, about $0.001 per call each, WO-014). Used by the new host too |
| S3 buckets | `telcron-dev-media-<account-id>`, `telcron-dev-raw-<account-id>` | Public access blocked. Media holds members' product photos (`photos/`), served through short-lived links (WO-014); raw holds the database backups (`backups/postgres/`, 14 days; `backups/rds-final/`) |
| ECR repository | `telcron/backend` | Holds the image of the first, manual deploy. The pipeline does not use it |
| Secret | `<app secret>` | `JWT_SECRET`, `APP_DB_PASSWORD`, `SEED_ADMIN_PASSWORD`, `PG_SUPERUSER_PASSWORD` (the host's PostgreSQL superuser); optional `LLM_API_KEY`, `GEMINI_API_KEY`, `MAIL_FROM`, `SMTP_PASSWORD`, `TAVILY_API_KEY`; never displayed |
| Secret (old) | RDS-managed master password | Deleted with RDS |
| Budget | `telcron-monthly` | USD 22 a month, cost budget |

Resources carry the tags `project=telcron`, `env=dev` where the service supports them.

## What it costs

Estimates from list prices, not from a bill. The account is on the AWS free plan, so this is drawn from
credit until the credit or the plan's six months run out. The human accepted the first layout on
2026-11-15 and the single host on 2026-11-21.

| Item (after the cutover) | USD a month |
| --- | --- |
| EC2 `t4g.small` | about 12.30 |
| EC2 disk, 20 GB | about 1.60 |
| EC2 public IPv4 (the Elastic IP) | about 3.65 |
| **The single host** | **about 17.50** |
| Lightsail (its static IP is free while attached) | 5.00 |
| One secret | 0.40 |
| S3 backups (14 small dumps) | under 0.05 |
| **Total** | **about 23** |

Before the cutover the total was about 33 (`t3.micro` 7.60, its disk 1.60, IPv4 3.65, RDS 11.70 and its
disk 2.30, Lightsail 5.00, two secrets 0.80). During the cutover both hosts run for an hour or two.

## Known gaps

- One host is a single point of failure: no managed backups, no failover, no point-in-time recovery.
  The nightly dump to S3 is the only copy; up to a day of data can be lost (ADR-007).
- The backend image is built on the 2 GB host at deploy time, beside the running stack. It works, with
  swap. A registry the host can read without new credentials would be better (prepared, waiting on
  the human: WO-020, DEF-006 item 4).
- The Lightsail host has port 22 open to the internet (key-only). It was needed to set the host up; it is
  not needed for releases and should be closed or restricted (prepared, waiting on the human: WO-020).
- The hostnames depend on a third-party wildcard-DNS service. A real domain removes that.
- The budget has no alert recipient, so it notifies nobody. After the cutover the total is close to it
  (prepared, waiting on the human: WO-020).
- No monitoring or alarms. Logs live only on the host.
- Bedrock: every model call on 2026-11-15 failed with `ThrottlingException: Too many tokens per day`.
  The account's quota is effectively zero, so hazard scoring is still the keyword placeholder.
- Two of the six "Earn AWS credits" activities are not done (EC2 was still "in progress"; the Bedrock
  playground is blocked by the quota).

## Removing something

Ask the human first, every time. The RDS instance has deletion protection: turn it off, then delete,
and decide deliberately whether to keep a final snapshot.
