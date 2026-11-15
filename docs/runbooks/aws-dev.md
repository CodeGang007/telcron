# AWS dev environment

Region `us-east-2`. The repository is public, so the account id, instance and security-group ids, IP
addresses and the database endpoint are **not** in this file. They are in the console and in
`docs/runbooks/aws-dev.local.md`, which is gitignored.

Everything below was created on 2026-11-15 from CloudShell in the console. No access keys exist.
**Nothing is deployed: the hosts are empty.** Deployment is WO-002.

## What exists

| Resource | Name | Notes |
| --- | --- | --- |
| EC2 instance | `telcron-dev-backend` | `t3.micro`, Ubuntu 24.04, 20 GB gp3 encrypted, IMDSv2 only, no key pair. For the API, the Worker and Redis in Docker |
| Lightsail instance | `telcron-dev-web` | Smallest bundle with a public IPv4, nginx blueprint. For the built frontend |
| RDS PostgreSQL | `telcron-dev` | 18.6, `db.t4g.micro`, 20 GB gp3 encrypted, single zone, not publicly reachable, deletion protection on, 1-day backups |
| Security group | `telcron-dev-backend` | Inbound 80 and 443 only |
| Security group | `telcron-dev-db` | Inbound 5432 from `telcron-dev-backend` only |
| IAM role and instance profile | `telcron-dev-backend` | Session Manager, ECR read, the two buckets, `telcron/dev/*` secrets, Bedrock invoke |
| S3 buckets | `telcron-dev-media-<account-id>`, `telcron-dev-raw-<account-id>` | Public access blocked |
| ECR repository | `telcron/backend` | Scan on push, immutable tags. Empty |
| Secret | `telcron/dev/app` | `JWT_SECRET`, generated in CloudShell and never displayed |
| Secret | RDS-managed master password | Created by RDS for user `telcron` |
| Budget | `telcron-monthly` | USD 22 a month, cost budget |

Resources carry the tags `project=telcron`, `env=dev`.

## What it costs

Estimates from list prices, not from a bill. The account is on the AWS free plan, so this is drawn
from credit until the credit or the plan's six months run out.

| Item | USD a month |
| --- | --- |
| EC2 `t3.micro` | about 7.60 |
| EC2 disk, 20 GB | about 1.60 |
| EC2 public IPv4 | about 3.65 |
| RDS `db.t4g.micro` | about 11.70 |
| RDS disk, 20 GB | about 2.30 |
| Lightsail | 5.00 |
| Two secrets | 0.80 |
| **Total** | **about 33** |

**This is over the USD 20 to 22 target.** The database is the difference. Running PostgreSQL in Docker
on the EC2 host next to Redis and deleting the RDS instance brings it to about USD 18. The price is one
gigabyte of memory shared by four processes and no managed backups. Awaiting the human's decision.

## Known gaps

- The budget has no alert recipient, so it notifies nobody.
- The Lightsail blueprint's default firewall leaves port 22 open as well as 80 and 443 (the blueprint's
  default; not checked in the console). The project rule is no port 22 open to the internet.
- The EC2 public address is not an Elastic IP: it changes on stop and start.
- The EC2 start-up script (Docker, 2 GB swap) was never checked for success.
- The EC2 role cannot read the RDS-managed secret (its policy covers `telcron/dev/*` only).
- Bedrock: every model call on 2026-11-15 failed with `ThrottlingException: Too many tokens per day`,
  from the CLI and the playground. The account's quota is effectively zero. The multimodal Titan
  embedding model was not in the region's model list; the text one was.

## Credit activities

Four of the six "Earn AWS credits" activities showed as completed on 2026-11-15: the budget, a Lambda
web app, a DynamoDB table, and one more. The Lambda function with its role and log group, the DynamoDB
table and a throwaway instance made for them were deleted afterwards. "Launch an instance using EC2"
still showed *In progress* at the last look, and the Bedrock playground activity could not be done
because of the quota above.

## Reaching it

Console, then CloudShell (it has the CLI and your console permissions). The EC2 host is reached
through Session Manager, not SSH. There is no SSH key and port 22 is closed on it.

## Removing something

Ask the human first, every time. The RDS instance has deletion protection: turn it off, then delete,
and decide deliberately whether to keep a final snapshot.
