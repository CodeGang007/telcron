#!/usr/bin/env bash
# Runs ON the AWS dev host, as root. Idempotent: run it again to redeploy.
# Normally started by agent-backend.sh when the release branch moves; it can also be run by hand
# through Session Manager.
#
# One host runs everything (ADR-007): Caddy, API, Worker, Redis, PostgreSQL and the embedder, in
# infra/aws/compose.yml. It reads secrets with the instance's own role. Nothing secret is passed in,
# printed, logged or put on a command line.
#
#   GIT_REF=<commit> API_HOST=<hostname> WEB_ORIGIN=<https://web host> \
#   [BACKEND_IMAGE=<registry/telcron/backend:tag>] [APP_SECRET_ID=telcron/dev/app] \
#   [AWS_REGION=us-east-2] [LOAD_SAMPLE=1] bash deploy-host.sh
#
# Without BACKEND_IMAGE the image is built on this host from the commit. With it, it is used as is
# (pulled first when it is in ECR).
# The app secret must hold JWT_SECRET, APP_DB_PASSWORD, SEED_ADMIN_PASSWORD and PG_SUPERUSER_PASSWORD;
# LLM_API_KEY, GEMINI_API_KEY, MAIL_FROM, SMTP_PASSWORD and TAVILY_API_KEY are optional.
set -euo pipefail

: "${GIT_REF:?}" "${API_HOST:?}" "${WEB_ORIGIN:?}"
# A host still set up for RDS (the layout before ADR-007) must not run this: it would start a second,
# empty database next to the real one. It keeps running its last release until it is deleted.
if [ -n "${DB_HOST:-}" ] || [ -n "${RDS_SECRET_ARN:-}" ]; then
  echo "this host is set up for RDS (DB_HOST/RDS_SECRET_ARN in deploy.env); releases after ADR-007 run" >&2
  echo "only on the single host. Not deploying. Stop this host's timer: systemctl disable --now telcron-deploy.timer" >&2
  exit 1
fi
APP_SECRET_ID=${APP_SECRET_ID:-telcron/dev/app}
REPO_URL=${REPO_URL:-https://github.com/CodeGang007/telcron.git}
ROOT=/opt/telcron
REPO=$ROOT/repo

say() { printf '==> %s\n' "$*"; }

say "host"
command -v docker >/dev/null || { echo "docker is missing: run infra/aws/setup-backend-host.sh first" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "the docker compose plugin is missing: run setup-backend-host.sh" >&2; exit 1; }
command -v git >/dev/null || { echo "git is missing: run setup-backend-host.sh" >&2; exit 1; }
mkdir -p "$ROOT"

say "code at $GIT_REF"
[ -d "$REPO/.git" ] || git clone -q --depth 1 "$REPO_URL" "$REPO"
git -C "$REPO" fetch -q --depth 1 origin "$GIT_REF"
git -C "$REPO" checkout -q --detach FETCH_HEAD

# The helpers come from the commit being deployed.
# shellcheck source=db-lib.sh
. "$REPO/infra/aws/db-lib.sh"

if [ -z "${BACKEND_IMAGE:-}" ]; then
  BACKEND_IMAGE="telcron-backend:${GIT_REF:0:12}"
  say "building $BACKEND_IMAGE on this host"
  docker build -q --build-arg GIT_SHA="$GIT_REF" -t "$BACKEND_IMAGE" "$REPO/backend" >/dev/null
fi

say "secrets"
app_secret=$(aws secretsmanager get-secret-value --secret-id "$APP_SECRET_ID" --query SecretString --output text)
JWT_SECRET=$(json_field JWT_SECRET <<<"$app_secret")
APP_DB_PASSWORD=$(json_field APP_DB_PASSWORD <<<"$app_secret")
SEED_ADMIN_PASSWORD=$(json_field SEED_ADMIN_PASSWORD <<<"$app_secret")
PG_SUPERUSER_PASSWORD=$(json_field PG_SUPERUSER_PASSWORD "" <<<"$app_secret")
if [ -z "$PG_SUPERUSER_PASSWORD" ]; then
  echo "the secret $APP_SECRET_ID has no PG_SUPERUSER_PASSWORD (the local PostgreSQL superuser's password)." >&2
  echo "Add one (for example 64 hex characters) to the secret; nothing is generated here." >&2
  exit 1
fi
# Optional: an API key for the hazard-scoring model. Without one the keyword placeholder scores.
LLM_API_KEY=$(json_field LLM_API_KEY "" <<<"$app_secret")
# Optional: the From address for verification codes. Without it codes are not emailed (WO-013).
MAIL_FROM=$(json_field MAIL_FROM "" <<<"$app_secret")
# Optional: an SMTP app password for MAIL_FROM (Gmail). With it codes go by SMTP, else by SES.
# Spaces are dropped: Google shows the app password in groups of four.
SMTP_PASSWORD=$(json_field SMTP_PASSWORD "" <<<"$app_secret")
SMTP_PASSWORD=${SMTP_PASSWORD// /}
MAIL_PROVIDER=log
if [ -n "$MAIL_FROM" ]; then MAIL_PROVIDER=$([ -n "$SMTP_PASSWORD" ] && echo smtp || echo ses); fi
# Optional: a Tavily key for product research's web search (WO-014).
TAVILY_API_KEY=$(json_field TAVILY_API_KEY "" <<<"$app_secret")
# Optional: a Gemini key, the last model in line when Groq's daily allowance is spent.
GEMINI_API_KEY=$(json_field GEMINI_API_KEY "" <<<"$app_secret")
# Product photos go to the private media bucket (created with the host, named after the account);
# Rekognition reads them. Both use the host's IAM role: no keys.
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
MEDIA_BUCKET=${MEDIA_BUCKET:-telcron-dev-media-$ACCOUNT_ID}
APP_DB_URL_PASSWORD=$(url_quote <<<"$APP_DB_PASSWORD")

say "environment files"
umask 077
cat > "$ROOT/.env" <<EOF
ENV=dev
BACKEND_IMAGE=$BACKEND_IMAGE
API_HOST=$API_HOST
WEB_ORIGIN=$WEB_ORIGIN
DATABASE_URL=postgresql://telcron_app:${APP_DB_URL_PASSWORD}@postgres:5432/${DB_NAME}
REDIS_URL=redis://redis:6379
JWT_SECRET=$JWT_SECRET
AI_PROVIDER=$([ -n "$LLM_API_KEY" ] && echo llm || echo stub)
LLM_API_KEY=$LLM_API_KEY
DEV_EXPOSE_CODES=false
MAIL_PROVIDER=$MAIL_PROVIDER
MAIL_FROM=$MAIL_FROM
SMTP_PASSWORD=$SMTP_PASSWORD
TAVILY_API_KEY=$TAVILY_API_KEY
GEMINI_API_KEY=$GEMINI_API_KEY
MEDIA_STORE=s3
MEDIA_BUCKET=$MEDIA_BUCKET
IMAGE_READER=rekognition
EOF
# Read by the postgres container only (the app containers never see the superuser's password). It
# takes effect when the data volume is first created; the role is updated below on every deploy.
cat > "$ROOT/postgres.env" <<EOF
POSTGRES_PASSWORD=$PG_SUPERUSER_PASSWORD
EOF

say "database"
compose build -q postgres embedder
compose up -d --wait postgres redis
# The application logs in as telcron_app, which owns the schema but is not a superuser. The
# superuser creates the extensions (postgis and vector are not trusted extensions), so the
# migration's own CREATE EXTENSION IF NOT EXISTS finds them there. Passwords travel on stdin.
{
  echo "ALTER ROLE postgres PASSWORD $(sql_literal "$PG_SUPERUSER_PASSWORD");"
  echo "SELECT 'CREATE ROLE telcron_app LOGIN' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telcron_app') \\gexec"
  echo "ALTER ROLE telcron_app NOSUPERUSER NOCREATEROLE NOCREATEDB PASSWORD $(sql_literal "$APP_DB_PASSWORD");"
  echo "ALTER DATABASE $DB_NAME OWNER TO telcron_app;"
  for ext in $DB_EXTENSIONS; do echo "CREATE EXTENSION IF NOT EXISTS $ext;"; done
} | pg postgres

say "migrations"
MIGRATE_DATABASE_URL="postgres://telcron_app:${APP_DB_URL_PASSWORD}@postgres:5432/${DB_NAME}?sslmode=disable" \
  compose run --rm -T migrate up

say "reference data"
# Phases 2-3 and their reference rows are migrations now (WO-022); `migrate up` above applies them.
pg telcron_app -f /db/seeds/001_core_reference.sql
if [ "${LOAD_SAMPLE:-0}" = "1" ]; then
  say "fictional demo data"
  pg telcron_app -f /db/seeds/dev/sample_data.sql
fi

say "start"
case "$BACKEND_IMAGE" in
  *.amazonaws.com/*)
    aws ecr get-login-password | docker login --username AWS --password-stdin "${BACKEND_IMAGE%%/*}" >/dev/null
    compose pull -q api worker
    ;;
esac
compose up -d --remove-orphans

say "seeded admin"
SEED_ADMIN_PASSWORD="$SEED_ADMIN_PASSWORD" compose run --rm -T -e SEED_ADMIN_PASSWORD api python -m app.seed

say "health"
for _ in $(seq 1 30); do
  if compose exec -T api python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')" 2>/dev/null; then
    compose ps --format 'table {{.Service}}\t{{.Status}}'
    # Keep the disk in check: the two newest locally built images stay, older ones go.
    docker images telcron-backend --format '{{.Repository}}:{{.Tag}}' | tail -n +3 | xargs -r docker rmi >/dev/null 2>&1 || true
    docker image prune -f >/dev/null 2>&1 || true
    say "deployed $GIT_REF"
    exit 0
  fi
  sleep 2
done
compose logs --tail 40 api
echo "the API did not become healthy" >&2
exit 1
