#!/usr/bin/env bash
# ONE-TIME: copies the dev database from RDS into the single host's PostgreSQL (ADR-007). Runs ON the
# new host, as root, through Session Manager, after its first deploy has finished.
#
#   OLD_DB_HOST=<rds endpoint> [OLD_DB_USER=telcron_app] [OLD_DB_PASSWORD=...] [FORCE=1] [KEEP_COPY=0] \
#   bash /opt/telcron/repo/infra/aws/migrate-from-rds.sh
#
# Credentials: by default it logs in to RDS as telcron_app, whose password is APP_DB_PASSWORD in the
# app secret (read here with the instance role) — telcron_app owns every table, so it can dump them
# all, and no password has to travel through Session Manager. OLD_DB_USER/OLD_DB_PASSWORD override
# that (for example the RDS master user); they are used for this run only and never stored.
#
# What it does:
#   1. refuses if this host's database already holds member data (FORCE=1 overrides);
#   2. stops the API and the Worker (the deploy agent is held off with its own lock);
#   3. pg_dump of RDS over TLS, custom format;
#   4. replaces the local database with it (db-lib.sh load_dump: extensions by the superuser,
#      everything else owned by telcron_app, triggers and foreign keys after the data);
#   5. compares RDS and the copy: exact row counts of every table, the number of tables, views,
#      indexes, constraints, triggers, functions and enum types, and every sequence's position.
#      Any difference stops here, with the API and Worker still stopped;
#   6. keeps the dump in S3 at backups/rds-final/<UTC time>.dump (KEEP_COPY=0 skips; outside the
#      nightly backups' 14-day clean-up);
#   7. runs deploy-host.sh for the checked-out commit: newer migrations and reference
#      data, then the API and Worker start again.
#
# Stop writes on the old host first (docker compose stop api worker there), or they are lost.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=db-lib.sh
. "$HERE/db-lib.sh"
: "${OLD_DB_HOST:?the RDS endpoint}"
OLD_DB_USER=${OLD_DB_USER:-telcron_app}
OLD_DB_NAME=${OLD_DB_NAME:-telcron}
[ -f "$ROOT/deploy.env" ] && [ -f "$ROOT/.env" ] || die "this host has not been deployed yet (no $ROOT/.env)"
set -a
# shellcheck source=/dev/null
. "$ROOT/deploy.env"
set +a
APP_SECRET_ID=${APP_SECRET_ID:-telcron/dev/app}

exec 9>"$ROOT/.deploy.lock"
flock -n 9 || die "a deploy is running; try again when it has finished"

say "target check"
compose up -d --wait postgres
if [ "$(pg postgres -Atc "select to_regclass('public.users') is not null")" != "t" ]; then
  die "the local database has no users table: let the first deploy finish, then run this"
fi
members=$(member_count)
if [ "$members" != "0" ] && [ "${FORCE:-0}" != "1" ]; then
  die "the local database already holds $members member account(s); refusing to overwrite (FORCE=1 overrides)"
fi

if [ -z "${OLD_DB_PASSWORD:-}" ]; then
  [ "$OLD_DB_USER" = "telcron_app" ] || die "OLD_DB_PASSWORD is needed for $OLD_DB_USER"
  OLD_DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id "$APP_SECRET_ID" --query SecretString \
                      --output text | json_field APP_DB_PASSWORD)
fi

# The RDS password goes into a pgpass file inside the container, through stdin: never on a command
# line, never in the environment of a long-lived process. Removed on exit.
pgpass=/tmp/.pgpass_rds
cleanup() {
  compose exec -T postgres rm -f "$pgpass" /tmp/rds.dump /tmp/fp_rds /tmp/fp_local >/dev/null 2>&1 || true
}
trap cleanup EXIT
escaped=${OLD_DB_PASSWORD//\\/\\\\}
escaped=${escaped//:/\\:}
compose exec -T postgres sh -c "umask 077; cat > $pgpass" <<<"$OLD_DB_HOST:5432:$OLD_DB_NAME:$OLD_DB_USER:$escaped"
unset escaped OLD_DB_PASSWORD
rds() { # rds <program> [arguments...] — a PostgreSQL client in the container, against RDS over TLS
  local prog=$1
  shift
  compose exec -T -e PGPASSFILE="$pgpass" -e PGSSLMODE=require -e PGCONNECT_TIMEOUT=10 postgres \
    "$prog" -h "$OLD_DB_HOST" -U "$OLD_DB_USER" -d "$OLD_DB_NAME" "$@"
}

say "source"
rds psql -Atc "select 'RDS ' || version()"

say "stop api and worker"
compose stop api worker

say "dump RDS"
rds pg_dump --format=custom --compress=6 -f /tmp/rds.dump
compose exec -T postgres pg_restore -l /tmp/rds.dump | grep -c '^[0-9]' | sed 's/^/entries: /'

load_dump /tmp/rds.dump

say "compare"
printf '%s\n' "$FINGERPRINT_SQL" | rds psql -At -F $'\t' -v ON_ERROR_STOP=1 -f - > "$ROOT/migrate-rds.tsv"
printf '%s\n' "$FINGERPRINT_SQL" | pg postgres -At -F $'\t' -f - > "$ROOT/migrate-local.tsv"
# Side by side, one line per table / object kind / sequence. Sorted here, byte-wise, so that the two
# servers' collations cannot make equal results look different.
report=$(LC_ALL=C join -t $'\t' -a 1 -a 2 -e '(none)' -o 0,1.2,2.2 \
    <(awk -F'\t' '{print $1" "$2"\t"$3}' "$ROOT/migrate-rds.tsv" | LC_ALL=C sort) \
    <(awk -F'\t' '{print $1" "$2"\t"$3}' "$ROOT/migrate-local.tsv" | LC_ALL=C sort) \
  | awk -F'\t' '{split($1, k, " "); n=$1; sub(/^[^ ]+ /, "", n);
                 printf "%-8s %-60s %12s %12s%s\n", k[1], n, $2, $3, ($2 == $3 ? "" : "   <-- differs")}')
printf '%-8s %-60s %12s %12s\n' kind name rds local
printf '%s\n' "$report"
[ -s "$ROOT/migrate-rds.tsv" ] || die "the fingerprint of RDS came back empty"
if grep -q -- '<-- differs' <<<"$report"; then
  die "the copy differs from RDS (lines marked above). The API and Worker are stopped; RDS is untouched."
fi
say "identical: $(grep -c '^rows' "$ROOT/migrate-local.tsv") tables, $(awk -F'\t' '$1=="rows"{s+=$3} END{print s+0}' "$ROOT/migrate-local.tsv") rows"
rm -f "$ROOT/migrate-rds.tsv" "$ROOT/migrate-local.tsv"

if [ "${KEEP_COPY:-1}" = "1" ]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  key="backups/rds-final/$(date -u +%Y%m%dT%H%M%SZ).dump"
  say "keep the RDS dump at s3://telcron-dev-raw-$ACCOUNT_ID/$key"
  mkdir -p "$ROOT/backups"
  compose cp postgres:/tmp/rds.dump "$ROOT/backups/rds-final.dump" >/dev/null
  aws s3 cp --only-show-errors "$ROOT/backups/rds-final.dump" "s3://telcron-dev-raw-$ACCOUNT_ID/$key"
  rm -f "$ROOT/backups/rds-final.dump"
fi

say "bring the schema forward and start everything"
current_image=$(sed -n 's/^BACKEND_IMAGE=//p' "$ROOT/.env")
GIT_REF=$(git -C "$REPO" rev-parse HEAD) BACKEND_IMAGE=$current_image bash "$REPO/infra/aws/deploy-host.sh"
say "migration from RDS done"
