# Outside services and their keys — how to add, replace or remove one

Every key lives in exactly two places, never in the repository:

- **Live (AWS):** a field of the Secrets Manager secret `telcron/dev/app` (region `us-east-2`). The
  server reads it on every deploy (`infra/aws/deploy-host.sh`) and writes it into its env file.
- **Your machine:** the gitignored `.env` at the repo root (`.env.example` lists the names).

A changed key takes effect on the **next deploy**. Any push to `main` deploys; to apply a key without
a code change, see "Apply now" below.

## What uses what

| Field | Service | Used for | Without it | Where to get one |
| --- | --- | --- | --- | --- |
| `LLM_API_KEY` | Groq | Hazard scoring, research reading, the assistant (gpt-oss-120b, then gpt-oss-20b); photo reading (qwen) | Keyword stub scores; no research reading; no assistant | console.groq.com → API keys (free plan: 200k tokens a day per model) |
| `GEMINI_API_KEY` | Google Gemini | Last model in line when both Groq models are spent for the day; also reads photos if Groq cannot (`gemini-flash-lite-latest`, the cheapest) | Nothing after Groq; research waits and retries every 20 min | aistudio.google.com → Get API key |
| `TAVILY_API_KEY` | Tavily | Research web searches (4 a product: web, regulators, owner reports, reviews) and marketplace listings | Falls back to Groq's built-in browser search, a few a day | tavily.com (free: 1,000 searches a month) |
| `MAIL_FROM` + `SMTP_PASSWORD` | Gmail (SMTP) | Sign-up verification codes | Codes are not emailed | Google account → 2-Step Verification on → myaccount.google.com/apppasswords |
| `JWT_SECRET`, `APP_DB_PASSWORD`, `PG_SUPERUSER_PASSWORD`, `SEED_ADMIN_PASSWORD` | Telcron itself | Sessions, database roles, the admin | The deploy refuses to run | Generated (`openssl rand -hex 32`); change only deliberately |

No key at all is needed for: CPSC, openFDA and UK OPSS (recall registries), UPCitemdb and Open Food
Facts (barcodes), Amazon Rekognition and S3 (the server's IAM role), and the embedding model (our own
`services/embedder`).

Model names are settings, not secrets: `LLM_MODEL`, `LLM_FALLBACK_MODEL`, `VISION_MODEL`,
`GEMINI_MODEL` in `backend/app/core/config.py` (override in `.env` or the server env file).

## Replace a key (live)

1. Sign in: `aws login` (CLI at `~/aws-cli/aws`).
2. Copy the new key to the clipboard, then run (set `FIELD` to the field name above). The key is read
   from the clipboard, so it never appears in the terminal, the shell history or a chat:

   ```bash
   export FIELD=GEMINI_API_KEY
   export V="$(pbpaste)"; ~/aws-cli/aws secretsmanager get-secret-value --region us-east-2 \
     --secret-id telcron/dev/app --query SecretString --output text \
   | python3 -c 'import json,os,sys; d=json.load(sys.stdin); d[os.environ["FIELD"]]=os.environ["V"].strip(); print(json.dumps(d))' \
   | ~/aws-cli/aws secretsmanager put-secret-value --region us-east-2 --secret-id telcron/dev/app \
     --secret-string file:///dev/stdin --query VersionId --output text; unset V
   ```
   It prints a version id.
3. Apply now (below), or wait for the next push.
4. Check: `curl https://<api host>/health` answers, and the feature works (for a model key: ask the
   product assistant a question; for Tavily: "Search again" on a product).

To **remove** a key, use the same command with `d.pop(os.environ["FIELD"], None)` instead of the
assignment, then apply.

## Replace a key (your machine)

Edit `.env`, then restart: `make dev-stop && make dev`.

## Apply now (redeploy without a code change)

The server redeploys when the release branch moves; to re-run the current release instead:

```bash
~/aws-cli/aws ssm send-command --region us-east-2 --document-name AWS-RunShellScript \
  --instance-ids <host instance id, see aws-dev.local.md> \
  --parameters 'commands=["rm -f /opt/telcron/.release /opt/telcron/.attempt && systemctl start telcron-deploy.service"]'
```
Then watch `journalctl -u telcron-deploy` (same command, `journalctl -u telcron-deploy -n 20 --no-pager`)
until it prints `deployed <commit>`.

## When a key leaks

Revoke it at the provider first (that is what stops misuse), then replace it as above. Keys pasted into
a chat, an issue or a commit count as leaked.

## Current status (update when it changes)

- `GEMINI_API_KEY` is **temporary** (borrowed from another project, 2026-11-22): replace it with a key
  from a Telcron Google project when one exists.
- `LLM_API_KEY`, `TAVILY_API_KEY` and the Gmail app password were shared in a chat: rotate when convenient.
