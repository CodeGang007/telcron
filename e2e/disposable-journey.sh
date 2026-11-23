#!/usr/bin/env bash
# `npm run journey`: the member's journey on a stack of its own, so the shared local database
# (and the demo products' passports) are left as they were (DEF-121).
#
#   1. a fresh database in the running telcron-db container, migrated and seeded as `make app-db` does
#   2. its own API (:4311), Worker and web dev server (:3201), on its own Redis index (9) of :6381
#   3. the journey against it
#   4. on exit, also on failure or Ctrl-C: the processes are stopped, the Redis index is emptied and
#      the database is dropped
#
# Runs the spec against an existing stack instead, exactly as before, when CI is set (the pipeline
# builds a throwaway stack of its own) or BASE_URL is given. `npm run journey:here` does the same.
# Overrides: E2E_API_PORT, E2E_WEB_PORT, E2E_REDIS_DB, E2E_KEEP=1 (leave the stack up to inspect it).
# Arguments go to Playwright: `npm run journey -- -g barcode`.
set -uo pipefail

if [ -n "${CI:-}" ] || [ -n "${BASE_URL:-}" ]; then exec npx playwright test journey "$@"; fi

E2E=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$E2E")
API_PORT=${E2E_API_PORT:-4311}
WEB_PORT=${E2E_WEB_PORT:-3201}
REDIS_DB=${E2E_REDIS_DB:-9}
DB_NAME="telcron_e2e_$(date +%s)_$$"
LOGS="$ROOT/.dev-logs"   # gitignored; e2e-*.log only, never a .pid (dev-all.sh stops every .pid there)

say() { printf '\033[36m[journey]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[journey]\033[0m %s\n' "$*" >&2; exit 2; }
# A setting from the repository's .env, else the default (only the database and Redis names are read).
env_file() { local v; v=$(grep -E "^$1=" "$ROOT/.env" 2>/dev/null | tail -n1 | cut -d= -f2-); echo "${v:-$2}"; }
port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
compose() { (cd "$ROOT" && docker compose "$@"); }

PG_USER=$(env_file POSTGRES_USER telcron)
PG_PASSWORD=$(env_file POSTGRES_PASSWORD telcron_dev)
DB_PORT=$(env_file DB_PORT 5440)
REDIS_PORT=$(env_file REDIS_PORT 6381)
psql_admin() { compose exec -T db psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 -qAt "$@"; }
redis() { compose exec -T redis redis-cli -n "$REDIS_DB" "$@"; }

# ── preconditions: nothing of ours is running, the shared containers are up ──────────────────────
for p in "$API_PORT" "$WEB_PORT"; do
  port_open "$p" && die "port $p is in use (another journey run?). Set E2E_API_PORT / E2E_WEB_PORT, or stop it."
done
compose exec -T db pg_isready -q -U "$PG_USER" >/dev/null 2>&1 || die "Postgres (telcron-db) is not up: make up"
[ "$(redis ping 2>/dev/null | tr -d '\r')" = PONG ] || die "Redis (telcron-redis) is not up: make up"
keys=$(redis dbsize | tr -d '\r')
[ "$keys" = 0 ] || die "Redis index $REDIS_DB holds $keys keys (a run that was killed?). Clear it with
  docker compose exec redis redis-cli -n $REDIS_DB flushdb      or pick another: E2E_REDIS_DB=n"
stale=$(psql_admin -c "select string_agg(datname, ' ') from pg_database where datname like 'telcron\_e2e\_%'")
[ -z "$stale" ] || say "left over from a killed run (drop them with DROP DATABASE … WITH (FORCE)): $stale"

# ── teardown, whatever happens from here on ───────────────────────────────────────────────────────
PIDS=()
kill_tree() { local c; for c in $(pgrep -P "$1"); do kill_tree "$c"; done; kill "$1" 2>/dev/null; }
alive() { local p; for p in "${PIDS[@]}"; do kill -0 "$p" 2>/dev/null && return 0; done; return 1; }
created_db=
cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [ -n "${E2E_KEEP:-}" ]; then
    say "E2E_KEEP: left up — web :$WEB_PORT, API :$API_PORT, database $DB_NAME, Redis index $REDIS_DB"
    say "pids ${PIDS[*]}; to remove: kill them, flushdb index $REDIS_DB, DROP DATABASE $DB_NAME WITH (FORCE)"
    exit "$status"
  fi
  say "stopping the disposable stack"
  for p in "${PIDS[@]}"; do kill_tree "$p"; done
  for _ in $(seq 1 20); do alive || break; sleep 0.5; done
  for p in "${PIDS[@]}"; do kill -0 "$p" 2>/dev/null && { pkill -KILL -P "$p"; kill -KILL "$p"; } 2>/dev/null; done
  redis flushdb >/dev/null
  [ -n "$created_db" ] && psql_admin -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)"
  say "removed: processes ${PIDS[*]:-none}, Redis index $REDIS_DB, database ${created_db:-none}"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# ── 1. the database, as `make app-db` builds it ──────────────────────────────────────────────────
say "database $DB_NAME"
psql_admin -c "CREATE DATABASE $DB_NAME" || exit 1
created_db=$DB_NAME
compose run --rm --no-deps -T \
  -e "DATABASE_URL=postgres://$PG_USER:$PG_PASSWORD@db:5432/$DB_NAME?sslmode=disable" \
  migrate up >"$LOGS/e2e-migrate.log" 2>&1 || { tail -n 30 "$LOGS/e2e-migrate.log"; exit 1; }
for f in "$ROOT"/db/seeds/0*_*.sql "$ROOT/db/seeds/dev/sample_data.sql"; do
  compose exec -T db psql -U "$PG_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -q <"$f" >>"$LOGS/e2e-migrate.log" 2>&1 \
    || { tail -n 30 "$LOGS/e2e-migrate.log"; exit 1; }
done

# The application's settings for this stack. The process environment wins over .env and .env.local.
export ENV=local
export DATABASE_URL="postgresql://$PG_USER:$PG_PASSWORD@127.0.0.1:$DB_PORT/$DB_NAME"
export REDIS_URL="redis://127.0.0.1:$REDIS_PORT/$REDIS_DB"
export WEB_ORIGIN="http://localhost:$WEB_PORT"
export VITE_API_URL="http://localhost:$API_PORT"
export DEV_EXPOSE_CODES=true
export COIN_CONFIRM_DELAY_SECONDS=2
# Recorded CPSC notices, as in the pipeline: the import test does not depend on the network.
export CPSC_FIXTURE=backend/tests/fixtures/cpsc_recalls.json
# An admin who exists only in this database; the journey reads the same variable.
SEED_ADMIN_PASSWORD=$(openssl rand -hex 16)
export SEED_ADMIN_PASSWORD
(cd "$ROOT/backend" && uv run -q python -m app.seed) >>"$LOGS/e2e-migrate.log" 2>&1 \
  || { tail -n 30 "$LOGS/e2e-migrate.log"; exit 1; }

# ── 2. the API, the Worker and the web app ───────────────────────────────────────────────────────
start() {  # name, directory, command...
  local name=$1 dir=$2; shift 2
  (cd "$dir" && exec "$@") >"$LOGS/e2e-$name.log" 2>&1 &
  PIDS+=($!)
}
start api "$ROOT/backend" uv run uvicorn app.main:app --port "$API_PORT"
start worker "$ROOT/backend" uv run python -m app.workers.main
start web "$ROOT/frontend" npx vite --config "$E2E/vite.disposable.config.mts" --port "$WEB_PORT" --strictPort
say "api :$API_PORT · worker · web :$WEB_PORT — logs in .dev-logs/e2e-*.log"
for _ in $(seq 1 90); do
  if curl -fsS "http://localhost:$API_PORT/health" >/dev/null 2>&1 && curl -fsS "http://localhost:$WEB_PORT/" >/dev/null 2>&1; then
    ready=1; break
  fi
  alive || break
  sleep 1
done
[ -n "${ready:-}" ] || { tail -n 30 "$LOGS"/e2e-{api,worker,web}.log; die "the stack did not start"; }

# ── 3. the journey ──────────────────────────────────────────────────────────────────────────────
# In the background and waited for, so an interrupt reaches the teardown at once (and stops it too).
(cd "$E2E" && BASE_URL="http://localhost:$WEB_PORT" exec npx playwright test journey "$@") &
PIDS+=($!)
wait "$!"
