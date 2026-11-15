#!/usr/bin/env bash
# One-time setup of the backend host's deploy agent. Runs ON the host, as root, through Session
# Manager. Idempotent. After this the host deploys by itself whenever the release branch moves.
#
#   API_HOST=<hostname> WEB_ORIGIN=<https://web host> DB_HOST=<rds endpoint> RDS_SECRET_ARN=<arn> \
#   [LOAD_SAMPLE=1] bash setup-backend-host.sh
#
# Expects agent-backend.sh next to this script.
set -euo pipefail
: "${API_HOST:?}" "${WEB_ORIGIN:?}" "${DB_HOST:?}" "${RDS_SECRET_ARN:?}"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=/opt/telcron
mkdir -p "$ROOT"

# These identify the environment; none is a secret. They stay on the host, out of the repository.
umask 077
cat > "$ROOT/deploy.env" <<EOF
API_HOST=$API_HOST
WEB_ORIGIN=$WEB_ORIGIN
DB_HOST=$DB_HOST
RDS_SECRET_ARN=$RDS_SECRET_ARN
LOAD_SAMPLE=${LOAD_SAMPLE:-0}
EOF
install -m 755 "$HERE/agent-backend.sh" "$ROOT/agent-backend.sh"

cat > /etc/systemd/system/telcron-deploy.service <<EOF
[Unit]
Description=Telcron: deploy the release branch if it moved
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$ROOT/agent-backend.sh
TimeoutStartSec=1800
EOF
cat > /etc/systemd/system/telcron-deploy.timer <<EOF
[Unit]
Description=Telcron: check the release branch every minute

[Timer]
OnBootSec=1min
OnUnitInactiveSec=1min
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now telcron-deploy.timer
systemctl is-active telcron-deploy.timer
