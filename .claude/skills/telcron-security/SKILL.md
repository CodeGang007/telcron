---
name: telcron-security
description: Telcron's security rules — identity and sessions, verification levels and roles, coins and fraud, ID documents, secrets, uploads, AI inputs and AWS access. Load before touching auth, any member-only route, the ledger, file uploads, a model prompt, or anything in AWS.
---

# Security

- **Sign-in.** Access JWTs last one hour. Refresh tokens last 30 days, are stored only as SHA-256 hashes and
  rotate on every use; a reused one revokes the whole family. Five bad passwords lock the account for 15 minutes.
  Codes are hashed, expire in 10 minutes and die after five wrong tries.
- **Access.** Every member route states its requirement through a `core/deps.py` dependency. Level 0 reads;
  Level 1 contributes; staff routes need `admin` or `moderator`. Another user's row is a 404.
- **Coins.** Written only through the database's `coin_*` functions: idempotency key on every entry, limits,
  daily cap, rapid-fire fraud hold, a row lock on the balance. Coins are never exchangeable for money.
- **ID documents.** Uploaded to a private S3 prefix, read by Textract, compared by Rekognition, then **deleted**.
  Only the result and the match score are stored. This is regulated personal data: do not log it, cache it or
  copy it anywhere else.
- **Secrets.** Local values in `.env.local` (gitignored). Deployed values in AWS Secrets Manager, read with the
  instance role. Never print, commit or paste a secret, including into a work order or a test.
- **Dev conveniences stay local.** `DEV_EXPOSE_CODES` returns verification codes in the response. It must be
  false, or absent, in every deployed environment. The seeded admin exists only when `ENV` is `local` or
  `dev` and `SEED_ADMIN_PASSWORD` is set; no credential is in the repository. The API refuses to start outside local
  with the default `JWT_SECRET`.
- **Uploads and AI.** Images pass a safety check and have location data removed before storage. User text that
  reaches a model prompt is data, never instructions; a score must cite evidence that exists.
- **Errors.** Never reveal whether an email is registered, a provider's error text, or a stack trace.
- **AWS.** No access keys, anywhere: people sign in with `aws login`, the EC2 host uses its role, and the
  pipeline holds no AWS credentials (the hosts pull their releases). Whoever can write to `release/dev` can
  deploy to dev. No port 22 or 5432 open to the internet. Creating, changing or deleting a resource
  needs the human's explicit yes, with the monthly cost stated. The repository is public: account ids,
  resource ids, addresses and endpoints go in `*.local.md` (gitignored), never in a tracked file.
