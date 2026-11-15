#!/bin/sh
# Starts the API (:4310), the Worker and the web app (:3200), detached, logs in .dev-logs/.
# Tracks its own PIDs and never kills by name: other projects run dev servers on this machine.
cd "$(dirname "$0")/.." || exit 1
mkdir -p .dev-logs
kill_tree() {
  for child in $(pgrep -P "$1"); do kill_tree "$child"; done
  kill "$1" 2>/dev/null
}
stop() {
  for f in .dev-logs/*.pid; do
    [ -f "$f" ] || continue
    kill_tree "$(cat "$f")"
    rm -f "$f"
  done
}
if [ "$1" = "stop" ]; then stop; echo stopped; exit 0; fi
stop
start() {  # name, directory, command...
  name=$1; dir=$2; shift 2
  ( cd "$dir" || exit 1; exec nohup "$@" > "../.dev-logs/$name.log" 2>&1 ) &
  echo $! > ".dev-logs/$name.pid"
}
start api backend uv run uvicorn app.main:app --port 4310
start worker backend uv run python -m app.workers.main
start web frontend npm run dev
echo "api :4310 · worker · web :3200 — logs in .dev-logs/"
