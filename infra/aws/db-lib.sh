#!/usr/bin/env bash
# Shared by deploy-host.sh, backup-db.sh, restore-db.sh and migrate-from-rds.sh on the single dev host
# (ADR-007). Sourced, never run. Nothing here prints a secret.
#
# Expects ROOT (default /opt/telcron) and REPO (default $ROOT/repo).

ROOT=${ROOT:-/opt/telcron}
REPO=${REPO:-$ROOT/repo}
DB_NAME=${DB_NAME:-telcron}
export AWS_REGION=${AWS_REGION:-us-east-2}
# The database's extensions. Created by the superuser, because postgis and vector are not trusted
# extensions and the application's role is not a superuser. Keep in step with
# db/migrations/20261114120000_extensions_and_types.sql.
DB_EXTENSIONS="citext pg_trgm btree_gist postgis vector"

say() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

compose() {
  TELCRON_ENV_FILE=$ROOT/.env TELCRON_PG_ENV_FILE=$ROOT/postgres.env \
    docker compose -f "$REPO/infra/aws/compose.yml" --env-file "$ROOT/.env" "$@"
}

# The host's own AWS CLI (Amazon Linux ships it), else the official image on the host network so that
# it can reach the instance metadata service for the role's credentials.
aws() {
  if type -P aws >/dev/null; then
    command aws "$@"
  else
    docker run --rm --network host -e AWS_REGION -e AWS_DEFAULT_REGION="$AWS_REGION" public.ecr.aws/aws-cli/aws-cli "$@"
  fi
}

# json_field <name> [default] < json   — a missing field is an error unless a default is given.
json_field() {
  python3 -c '
import json, sys
data = json.load(sys.stdin)
name = sys.argv[1]
if name in data:
    print(data[name])
elif len(sys.argv) > 2:
    print(sys.argv[2])
else:
    sys.exit(f"field {name} is missing")
' "$@"
}

# sql_literal <value>  -> the value as a quoted SQL string literal (for SQL sent on stdin, never argv).
sql_literal() { local v=${1//\'/\'\'}; printf "'%s'" "$v"; }

# url_quote < value  -> percent-encoded, for a password inside a connection URL.
url_quote() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.stdin.read().rstrip("\n"), safe=""))'; }

# pg <user> [psql arguments...] — psql inside the postgres container, over its Unix socket.
pg() {
  local user=$1
  shift
  compose exec -T postgres psql -U "$user" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q "$@"
}

# The target holds member data when it has any user other than the seeded admin and the fictional
# demo accounts (db/seeds/dev/sample_data.sql uses @telcron.local).
member_count() {
  pg postgres -Atc "select count(*) from users
                     where email <> 'admin@telcron.example.com' and email::text not like '%@telcron.local'"
}

# load_dump <path inside the postgres container>
# Replaces the database with the dump's contents. The database is dropped and created again, owned by
# telcron_app; the extensions are created by the superuser; everything else is restored AS telcron_app
# (--role), so the application owns its tables, functions and triggers exactly as after a migration.
# Grants and owners in the dump are ignored (the source may be RDS, with rds_superuser and a master
# user that do not exist here). Triggers and foreign keys are created after the data, so the
# append-only rules do not fire during the load. All or nothing: one transaction, stop at the first error.
load_dump() {
  local dump=$1 ext
  say "fresh database $DB_NAME"
  compose exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q <<SQL
DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE);
CREATE DATABASE $DB_NAME OWNER telcron_app;
SQL
  for ext in $DB_EXTENSIONS; do
    pg postgres -c "CREATE EXTENSION IF NOT EXISTS $ext"
  done
  say "restore"
  # Leave out what the superuser already made, or what the application's role may not touch: the
  # extensions, their comments, the public schema itself and data of extension tables (spatial_ref_sys).
  compose exec -T postgres sh -ec "pg_restore -l '$dump' > /tmp/full.list
    grep -vE '^[0-9]+; [0-9]+ [0-9]+ (EXTENSION - |COMMENT - EXTENSION |SCHEMA - public |COMMENT - SCHEMA public |TABLE DATA public spatial_ref_sys )' \
      /tmp/full.list > /tmp/restore.list"
  compose exec -T postgres pg_restore -U postgres -d "$DB_NAME" --role=telcron_app --no-owner --no-privileges \
    --exit-on-error --single-transaction -L /tmp/restore.list "$dump"
  compose exec -T postgres rm -f /tmp/full.list /tmp/restore.list
  compose exec -T postgres vacuumdb -U postgres -d "$DB_NAME" --analyze-only -q
}

# A fingerprint of a database: exact row counts of every table, the number of each kind of object, and
# each sequence's position. Objects that belong to an extension are left out (their versions may differ
# between RDS and this host). Same query on both sides; the outputs are compared line by line.
# shellcheck disable=SC2034  # used by migrate-from-rds.sh
FINGERPRINT_SQL=$(cat <<'SQL'
WITH ext AS (
  SELECT objid FROM pg_depend WHERE deptype = 'e' AND classid = 'pg_class'::regclass
), rels AS (
  SELECT c.oid, c.relkind, n.nspname, c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
     AND n.nspname NOT LIKE 'pg\_toast%' AND n.nspname NOT LIKE 'pg\_temp%'
     AND c.oid NOT IN (SELECT objid FROM ext)
)
SELECT kind, name, value FROM (
  SELECT 'rows' AS kind, format('%I.%I', nspname, relname) AS name,
         (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', nspname, relname),
                                               false, true, '')))[1]::text AS value
    FROM rels WHERE relkind IN ('r', 'p')
  UNION ALL
  SELECT 'count', 'tables', count(*)::text FROM rels WHERE relkind IN ('r', 'p')
  UNION ALL
  SELECT 'count', 'views', count(*)::text FROM rels WHERE relkind IN ('v', 'm')
  UNION ALL
  SELECT 'count', 'indexes', count(*)::text FROM rels r
   WHERE relkind IN ('i', 'I')
     AND NOT EXISTS (SELECT 1 FROM pg_index i WHERE i.indexrelid = r.oid AND i.indrelid IN (SELECT objid FROM ext))
  UNION ALL
  SELECT 'count', 'constraints', count(*)::text FROM pg_constraint k
   WHERE k.conrelid IN (SELECT oid FROM rels)
  UNION ALL
  SELECT 'count', 'triggers', count(*)::text FROM pg_trigger t
   WHERE NOT t.tgisinternal AND t.tgrelid IN (SELECT oid FROM rels)
  UNION ALL
  SELECT 'count', 'functions', count(*)::text FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
     AND NOT EXISTS (SELECT 1 FROM pg_depend d
                      WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e')
  UNION ALL
  SELECT 'count', 'enum types', count(*)::text FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
   WHERE t.typtype = 'e' AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  UNION ALL
  SELECT 'sequence', format('%I.%I', schemaname, sequencename), coalesce(last_value::text, 'unused')
    FROM pg_sequences WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
) f
ORDER BY kind, name;
SQL
)
