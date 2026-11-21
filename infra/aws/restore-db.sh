#!/usr/bin/env bash
# Replaces the dev database with a backup made by backup-db.sh. Runs ON the single dev host, as root,
# through Session Manager. DESTRUCTIVE: everything written since that backup is lost.
#
#   CONFIRM=replace-the-database [DUMP_KEY=backups/postgres/YYYY/MM/DD.dump | DUMP_FILE=/path/x.dump] \
#   bash /opt/telcron/repo/infra/aws/restore-db.sh
#
# Without DUMP_KEY or DUMP_FILE it takes the newest object under backups/postgres/. Afterwards it runs
# deploy-host.sh for the commit that is checked out, which brings the schema forward (newer migrations,
# phases 2-3, reference data) and starts the API and Worker again.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=db-lib.sh
. "$HERE/db-lib.sh"
[ "${CONFIRM:-}" = "replace-the-database" ] || die "set CONFIRM=replace-the-database: this replaces the whole database"
type -P aws >/dev/null || die "the host's aws CLI is needed"

exec 9>"$ROOT/.deploy.lock"
flock -n 9 || die "a deploy is running; try again when it has finished"

file=${DUMP_FILE:-}
if [ -z "$file" ]; then
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  BUCKET=${BACKUP_BUCKET:-telcron-dev-raw-$ACCOUNT_ID}
  key=${DUMP_KEY:-$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix backups/postgres/ \
                      --query 'sort_by(Contents, &LastModified)[-1].Key' --output text)}
  [ -n "$key" ] && [ "$key" != "None" ] || die "no backup found"
  file=$ROOT/backups/restore.dump
  mkdir -p "$ROOT/backups"
  say "download s3://$BUCKET/$key"
  aws s3 cp --only-show-errors "s3://$BUCKET/$key" "$file"
fi
[ -s "$file" ] || die "$file is missing or empty"

say "stop api and worker"
compose stop api worker
compose cp "$file" postgres:/tmp/restore.dump >/dev/null
load_dump /tmp/restore.dump
compose exec -T postgres rm -f /tmp/restore.dump
[ -n "${DUMP_FILE:-}" ] || rm -f "$file"

say "bring the schema forward and start everything"
set -a
# shellcheck source=/dev/null
. "$ROOT/deploy.env"
set +a
current_image=$(sed -n 's/^BACKEND_IMAGE=//p' "$ROOT/.env")
GIT_REF=$(git -C "$REPO" rev-parse HEAD) BACKEND_IMAGE=$current_image bash "$REPO/infra/aws/deploy-host.sh"
