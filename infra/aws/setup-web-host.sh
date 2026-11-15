#!/usr/bin/env bash
# One-time setup of the Lightsail web host (Debian 12). Runs ON the host, as a user with sudo.
# Idempotent. After this the host serves whatever web build the release branch holds.
#
#   WEB_HOST=<hostname> bash setup-web-host.sh
#
# Expects web.Caddyfile and agent-web.sh next to this script.
#
# The instance was created from the "nginx" blueprint, which also runs MariaDB, PHP, phpMyAdmin and
# Varnish. None of that is used: it is stopped and disabled, and Caddy serves the static files.
set -euo pipefail
: "${WEB_HOST:?}"
HERE=$(cd "$(dirname "$0")" && pwd)

say() { printf '==> %s\n' "$*"; }

if systemctl is-enabled --quiet bitnami 2>/dev/null || systemctl is-active --quiet bitnami 2>/dev/null; then
  say "stopping the unused blueprint stack"
  sudo systemctl disable --now bitnami
fi

if ! command -v caddy >/dev/null || ! command -v git >/dev/null; then
  say "installing caddy and git"
  sudo apt-get update -q
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q caddy git
fi

say "caddy configuration for $WEB_HOST"
sudo mkdir -p /var/www/telcron
sed "s/^WEB_HOST {/$WEB_HOST {/" "$HERE/web.Caddyfile" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1
sudo systemctl enable --now caddy
sudo systemctl reload caddy

say "deploy agent"
sudo mkdir -p /opt/telcron-web
sudo install -m 755 "$HERE/agent-web.sh" /opt/telcron-web/agent-web.sh
sudo tee /etc/systemd/system/telcron-web-deploy.service >/dev/null <<'EOF'
[Unit]
Description=Telcron: install the web build from the release branch if it moved
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/telcron-web/agent-web.sh
TimeoutStartSec=300
EOF
sudo tee /etc/systemd/system/telcron-web-deploy.timer >/dev/null <<'EOF'
[Unit]
Description=Telcron: check the release branch every minute

[Timer]
OnBootSec=1min
OnUnitInactiveSec=1min
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now telcron-web-deploy.timer

say "listening"
sudo ss -ltnp | awk 'NR>1 {print $4, $6}' | grep -E ':(80|443|22|3306|5432) ' || true
systemctl is-active caddy telcron-web-deploy.timer
