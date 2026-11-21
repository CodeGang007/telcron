#!/usr/bin/env bash
# Nightly database backup on the single dev host (ADR-007). Run by telcron-backup.timer at 02:30 UTC,
# as root; can be run by hand through Session Manager.
#
#   [BACKUP_BUCKET=<bucket>] [KEEP_DAYS=14] bash backup-db.sh
#
# Writes s3://telcron-dev-raw-<account id>/backups/postgres/YYYY/MM/DD.dump (pg_dump custom format,
# compressed), checks the file can be read back, and deletes backups older than KEEP_DAYS. Uses the
# instance role: s3:PutObject, s3:ListBucket and s3:DeleteObject on that bucket.
# To restore one: infra/aws/restore-db.sh (see docs/runbooks/aws-dev.md).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=db-lib.sh
. "$HERE/db-lib.sh"
KEEP_DAYS=${KEEP_DAYS:-14}
PREFIX=backups/postgres
type -P aws >/dev/null || die "the host's aws CLI is needed (setup-backend-host.sh installs it)"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET=${BACKUP_BUCKET:-telcron-dev-raw-$ACCOUNT_ID}
key="$PREFIX/$(date -u +%Y/%m/%d).dump"
work=$ROOT/backups
mkdir -p "$work"
chmod 700 "$work"
file=$work/telcron.dump
trap 'rm -f "$file"; compose exec -T postgres rm -f /tmp/backup.dump >/dev/null 2>&1 || true' EXIT

say "dump"
compose exec -T postgres pg_dump -U postgres -d "$DB_NAME" --format=custom --compress=6 -f /tmp/backup.dump
compose cp postgres:/tmp/backup.dump "$file" >/dev/null
# A dump that cannot be listed back is not a backup.
entries=$(compose exec -T postgres pg_restore -l /tmp/backup.dump | grep -c '^[0-9]')
[ "$entries" -gt 0 ] || die "the dump lists no entries"
say "$(du -h "$file" | cut -f1) in $entries entries"

say "upload to s3://$BUCKET/$key"
aws s3 cp --only-show-errors "$file" "s3://$BUCKET/$key"

say "remove backups older than $KEEP_DAYS days"
cutoff=$(date -u -d "$KEEP_DAYS days ago" +%Y-%m-%dT%H:%M:%SZ)
old=$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "$PREFIX/" \
        --query "Contents[?LastModified<'$cutoff'].Key" --output text)
for k in $old; do
  [ "$k" = "None" ] && continue
  aws s3 rm --only-show-errors "s3://$BUCKET/$k"
  echo "removed $k"
done
say "backup done"
