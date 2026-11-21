# AWS dev environment

Region `us-east-2`. The repository is public, so the account id, resource ids, IP addresses, hostnames
and the database endpoint are **not** in this file. They are in the console, in the repository's Actions
variables (`DEV_WEB_URL`, `DEV_API_URL`) and in `docs/runbooks/aws-dev.local.md`, which is gitignored.

The dev site has been live since 2026-11-16. Nobody holds AWS access keys: people use the console or
`aws login`; the EC2 host uses its instance role; GitHub holds no AWS credentials at all.

## What runs where

| Where | What |
| --- | --- |
| EC2 `telcron-dev-backend` (`t3.micro`, Ubuntu 24.04) | Docker Compose: Caddy (HTTPS), API, Worker, Redis. `infra/aws/compose.yml` |
| RDS `telcron-dev` (PostgreSQL 18, `db.t4g.micro`) | The database. Private; reachable from the EC2 host only |
| Lightsail `telcron-dev-web` (Debian 12, smallest bundle) | Caddy serving the built web app from `/var/www/telcron` |

Both public hosts have a fixed address and a hostname that encodes it (a wildcard-DNS service), with
Let's Encrypt certificates that Caddy obtains and renews. A real domain would replace both.

## How a release happens

1. A push to `main` runs `.github/workflows/pipeline.yml`: schema tests, backend lint and tests, web
   typecheck and build, and the member's journey in a browser against a full stack.
2. If all of it passes, the `release` job builds the web app, and commits it with a `VERSION` file naming
   the commit to the `release/dev` branch. That is the whole release: a commit on a branch.
3. Each host runs a small agent from a systemd timer, once a minute. It asks GitHub where `release/dev`
   points. When that has moved:
   - the EC2 host (`infra/aws/agent-backend.sh` → `deploy-host.sh`) checks out the commit, builds the
     backend image, creates or updates the application's database role, runs the migrations, loads
     reference data and phases 2-3, restarts the stack and seeds the admin;
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
aws login                                   # your own sign-in; region us-east-2
# what the backend host's agent did last
aws ssm send-command --document-name AWS-RunShellScript --instance-ids <instance id> \
  --parameters 'commands=["journalctl -u telcron-deploy -n 60 --no-pager"]'
aws ssm get-command-invocation --command-id <id> --instance-id <instance id> --query StandardOutputContent --output text
# on the host: docker compose -f /opt/telcron/repo/infra/aws/compose.yml --env-file /opt/telcron/.env ps
```

The EC2 host is reached through Session Manager; it has no SSH key and port 22 is closed. The Lightsail
host is reached with the account's Lightsail key over SSH; its agent logs to `journalctl -u telcron-web-deploy`.

To deploy by hand, run `infra/aws/deploy-host.sh` on the EC2 host with the variables its header lists.
To set a host up again from nothing: `infra/aws/setup-backend-host.sh`, `infra/aws/setup-web-host.sh`.

## Signing in to the dev site

Sign-up is closed there: the application cannot send verification codes yet (WO-005), and codes are never
shown on a deployed build. One admin exists, `admin@telcron.example.com`; its password is the
`SEED_ADMIN_PASSWORD` field of the `telcron/dev/app` secret. The demo products are fictional.

## What exists

| Resource | Name | Notes |
| --- | --- | --- |
| EC2 instance | `telcron-dev-backend` | 20 GB gp3 encrypted, IMDSv2 only, no key pair, 2 GB swap |
| Elastic IP | `telcron-dev-backend` | Attached to the instance |
| Lightsail instance, static IP | `telcron-dev-web`, `telcron-dev-web-ip` | The blueprint's own stack (nginx, MariaDB, PHP, phpMyAdmin, Varnish) is stopped and disabled |
| RDS PostgreSQL | `telcron-dev` | 20 GB gp3 encrypted, single zone, not publicly reachable, deletion protection, 1-day backups |
| Security groups | `telcron-dev-backend`, `telcron-dev-db` | 80 and 443 in; 5432 from the backend group only |
| IAM role and instance profile | `telcron-dev-backend` | Session Manager, ECR read, the two buckets, `telcron/dev/*` secrets, the RDS master secret, Bedrock invoke, SES send (`telcron-dev-ses-send`), Rekognition DetectText/DetectLabels (`telcron-dev-rekognition`, about $0.001 per call each, WO-014) |
| S3 buckets | `telcron-dev-media-<account-id>`, `telcron-dev-raw-<account-id>` | Public access blocked. Media holds members' product photos (`photos/`), served through short-lived links (WO-014); raw is not used yet |
| ECR repository | `telcron/backend` | Holds the image of the first, manual deploy. The pipeline does not use it |
| Secret | `telcron/dev/app` | `JWT_SECRET`, `APP_DB_PASSWORD`, `SEED_ADMIN_PASSWORD`; optional `LLM_API_KEY`, `MAIL_FROM`, `SMTP_PASSWORD`, `TAVILY_API_KEY`; never displayed |
| Secret | RDS-managed master password | Rotated by RDS. Used only to create the application's role |
| Budget | `telcron-monthly` | USD 22 a month, cost budget |

Resources carry the tags `project=telcron`, `env=dev` where the service supports them.

## What it costs

Estimates from list prices, not from a bill. The account is on the AWS free plan, so this is drawn from
credit until the credit or the plan's six months run out. The human accepted this on 2026-11-15.

| Item | USD a month |
| --- | --- |
| EC2 `t3.micro` | about 7.60 |
| EC2 disk, 20 GB | about 1.60 |
| EC2 public IPv4 (the Elastic IP; it replaced the instance's own, same price) | about 3.65 |
| RDS `db.t4g.micro` | about 11.70 |
| RDS disk, 20 GB | about 2.30 |
| Lightsail (its static IP is free while attached) | 5.00 |
| Two secrets | 0.80 |
| **Total** | **about 33** |

If the cost has to come down: PostgreSQL in Docker on the EC2 host instead of RDS brings it to about 18.

## Known gaps

- The application's database role, `telcron_app`, holds `rds_superuser`, because it also creates the
  extensions and runs the migrations. Production needs a narrower role and a separate migration step.
- The backend image is built on the 1 GB host at deploy time. It works, and it is slow and competes with
  the running stack for memory. A registry the host can read without new credentials would be better.
- The Lightsail host has port 22 open to the internet (key-only). It was needed to set the host up; it is
  not needed for releases and should be closed or restricted.
- The hostnames depend on a third-party wildcard-DNS service. A real domain removes that.
- The budget has no alert recipient, so it notifies nobody.
- No backups beyond RDS's one day. No monitoring or alarms. Logs live only on the hosts.
- Bedrock: every model call on 2026-11-15 failed with `ThrottlingException: Too many tokens per day`.
  The account's quota is effectively zero, so hazard scoring is still the keyword placeholder.
- Two of the six "Earn AWS credits" activities are not done (EC2 was still "in progress"; the Bedrock
  playground is blocked by the quota).

## Removing something

Ask the human first, every time. The RDS instance has deletion protection: turn it off, then delete,
and decide deliberately whether to keep a final snapshot.
