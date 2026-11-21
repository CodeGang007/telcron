#!/usr/bin/env bash
# Runs ON the AWS dev host, as root. Idempotent: run it again to redeploy.
# Normally started by agent-backend.sh when the release branch moves; it can also be run by hand
# through Session Manager.
#
# It reads secrets with the instance's own role. Nothing secret is passed in, printed or logged.
#
#   GIT_REF=<commit> API_HOST=<hostname> WEB_ORIGIN=<https://web host> DB_HOST=<rds endpoint> \
#   RDS_SECRET_ARN=<arn> [BACKEND_IMAGE=<registry/telcron/backend:tag>] [APP_SECRET_ID=telcron/dev/app] \
#   [AWS_REGION=us-east-2] [LOAD_SAMPLE=1] bash deploy-host.sh
#
# Without BACKEND_IMAGE the image is built on this host from the commit. With it, it is pulled.
# The app secret must hold JWT_SECRET, APP_DB_PASSWORD and SEED_ADMIN_PASSWORD; LLM_API_KEY, MAIL_FROM, SMTP_PASSWORD and TAVILY_API_KEY are optional.
set -euo pipefail

: "${GIT_REF:?}" "${API_HOST:?}" "${WEB_ORIGIN:?}" "${DB_HOST:?}" "${RDS_SECRET_ARN:?}"
APP_SECRET_ID=${APP_SECRET_ID:-telcron/dev/app}
export AWS_REGION=${AWS_REGION:-us-east-2}
DB_NAME=${DB_NAME:-telcron}
REPO_URL=${REPO_URL:-https://github.com/CodeGang007/telcron.git}
ROOT=/opt/telcron
REPO=$ROOT/repo

say() { printf '==> %s\n' "$*"; }

# Host networking so the containers can reach the instance metadata service for the role's credentials.
aws() { docker run --rm --network host -e AWS_REGION -e AWS_DEFAULT_REGION="$AWS_REGION" public.ecr.aws/aws-cli/aws-cli "$@"; }
field() { python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"; }
psql_as() { # psql_as <user> <password> [psql arguments...]
  local user=$1 password=$2
  shift 2
  docker run --rm -i --network host -e PGPASSWORD="$password" -e PGSSLMODE=require -v "$REPO/db:/db:ro" \
    postgres:18-alpine psql -h "$DB_HOST" -U "$user" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q "$@"
}
compose() { docker compose -f "$REPO/infra/aws/compose.yml" --env-file "$ROOT/.env" "$@"; }

say "host"
command -v docker >/dev/null || { apt-get update -q && apt-get install -y -q docker.io docker-compose-v2 && systemctl enable --now docker; }
command -v git >/dev/null || apt-get install -y -q git
mkdir -p "$ROOT"

say "code at $GIT_REF"
[ -d "$REPO/.git" ] || git clone -q --depth 1 "$REPO_URL" "$REPO"
git -C "$REPO" fetch -q --depth 1 origin "$GIT_REF"
git -C "$REPO" checkout -q --detach FETCH_HEAD

if [ -z "${BACKEND_IMAGE:-}" ]; then
  BACKEND_IMAGE="telcron-backend:${GIT_REF:0:12}"
  say "building $BACKEND_IMAGE on this host"
  docker build -q --build-arg GIT_SHA="$GIT_REF" -t "$BACKEND_IMAGE" "$REPO/backend" >/dev/null
fi

say "secrets"
app_secret=$(aws secretsmanager get-secret-value --secret-id "$APP_SECRET_ID" --query SecretString --output text)
JWT_SECRET=$(field JWT_SECRET <<<"$app_secret")
APP_DB_PASSWORD=$(field APP_DB_PASSWORD <<<"$app_secret")
SEED_ADMIN_PASSWORD=$(field SEED_ADMIN_PASSWORD <<<"$app_secret")
# Optional: an API key for the hazard-scoring model. Without one the keyword placeholder scores.
LLM_API_KEY=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("LLM_API_KEY", ""))' <<<"$app_secret")
# Optional: the From address for verification codes. Without it codes are not emailed (WO-013).
MAIL_FROM=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("MAIL_FROM", ""))' <<<"$app_secret")
# Optional: an SMTP app password for MAIL_FROM (Gmail). With it codes go by SMTP, else by SES.
# Spaces are dropped: Google shows the app password in groups of four.
SMTP_PASSWORD=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("SMTP_PASSWORD", "").replace(" ", ""))' <<<"$app_secret")
# Optional: a Tavily key for product research's web search (WO-014).
TAVILY_API_KEY=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("TAVILY_API_KEY", ""))' <<<"$app_secret")
# Product photos go to the private media bucket (created with the host, named after the account);
# Rekognition reads them. Both use the host's IAM role: no keys.
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
MEDIA_BUCKET=${MEDIA_BUCKET:-telcron-dev-media-$ACCOUNT_ID}
MAIL_PROVIDER=log
if [ -n "$MAIL_FROM" ]; then MAIL_PROVIDER=$([ -n "$SMTP_PASSWORD" ] && echo smtp || echo ses); fi
master=$(aws secretsmanager get-secret-value --secret-id "$RDS_SECRET_ARN" --query SecretString --output text)
MASTER_USER=$(field username <<<"$master")
MASTER_PASSWORD=$(field password <<<"$master")

# The master password is managed and rotated by RDS, so the application does not use it. It logs in
# as telcron_app, whose password lives in the app secret. For this dev environment that role holds
# rds_superuser (it creates extensions and runs the migrations); production needs a narrower one.
say "database role and extensions"
psql_as "$MASTER_USER" "$MASTER_PASSWORD" -v app_password="$APP_DB_PASSWORD" <<'SQL'
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
SELECT format('CREATE ROLE telcron_app LOGIN')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telcron_app') \gexec
ALTER ROLE telcron_app PASSWORD :'app_password';
GRANT rds_superuser TO telcron_app;
GRANT ALL ON DATABASE telcron TO telcron_app;
GRANT ALL ON SCHEMA public TO telcron_app;
SQL

say "migrations"
docker run --rm --network host -v "$REPO/db:/db:ro" \
  -e DATABASE_URL="postgres://telcron_app:${APP_DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}?sslmode=require" \
  -e DBMATE_MIGRATIONS_DIR=/db/migrations -e DBMATE_NO_DUMP_SCHEMA=true \
  ghcr.io/amacneil/dbmate:2 up

say "reference data and phases 2-3"
psql_as telcron_app "$APP_DB_PASSWORD" -f /db/seeds/001_core_reference.sql
if [ "$(psql_as telcron_app "$APP_DB_PASSWORD" -Atc "select to_regclass('hazard_assessments') is not null")" != "t" ]; then
  for f in phase2_schema phase2_rules phase3_schema phase3_rules; do
    psql_as telcron_app "$APP_DB_PASSWORD" -1 -f "/db/schema-next/$f.sql"
  done
fi
psql_as telcron_app "$APP_DB_PASSWORD" -f /db/schema-next/seed_reference.sql
if [ "${LOAD_SAMPLE:-0}" = "1" ]; then
  say "fictional demo data"
  psql_as telcron_app "$APP_DB_PASSWORD" -f /db/seeds/dev/sample_data.sql
fi

say "environment file"
umask 077
cat > "$ROOT/.env" <<EOF
ENV=dev
BACKEND_IMAGE=$BACKEND_IMAGE
API_HOST=$API_HOST
WEB_ORIGIN=$WEB_ORIGIN
DATABASE_URL=postgresql://telcron_app:${APP_DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}?ssl=require
REDIS_URL=redis://redis:6379
JWT_SECRET=$JWT_SECRET
AI_PROVIDER=$([ -n "$LLM_API_KEY" ] && echo llm || echo stub)
LLM_API_KEY=$LLM_API_KEY
DEV_EXPOSE_CODES=false
MAIL_PROVIDER=$MAIL_PROVIDER
MAIL_FROM=$MAIL_FROM
SMTP_PASSWORD=$SMTP_PASSWORD
TAVILY_API_KEY=$TAVILY_API_KEY
MEDIA_STORE=s3
MEDIA_BUCKET=$MEDIA_BUCKET
IMAGE_READER=rekognition
EOF

say "start"
case "$BACKEND_IMAGE" in
  *.amazonaws.com/*)
    aws ecr get-login-password | docker login --username AWS --password-stdin "${BACKEND_IMAGE%%/*}" >/dev/null
    compose pull -q api worker
    ;;
esac
compose up -d --remove-orphans

say "seeded admin"
compose run --rm -T -e SEED_ADMIN_PASSWORD="$SEED_ADMIN_PASSWORD" api python -m app.seed

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
