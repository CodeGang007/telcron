#!/usr/bin/env bash
# One-time setup of the single dev host (ADR-007): Amazon Linux 2023 on EC2 t4g.small (arm64; x86_64
# works too). Runs ON the host, as root: from EC2 user-data at first boot, or through Session Manager.
# Idempotent. After this the host deploys itself whenever the release branch moves, and backs the
# database up to S3 every night.
#
#   API_HOST=<hostname> WEB_ORIGIN=<https://web host> [LOAD_SAMPLE=0] [APP_SECRET_ID=telcron/dev/app] \
#   [AWS_REGION=us-east-2] bash setup-backend-host.sh
#
# Expects agent-backend.sh next to this script (it runs from a clone of the repository); the backup
# timer runs backup-db.sh from the deployed commit. No secret is passed in: the deploy reads them with
# the instance role.
#
# As EC2 user-data (the values are not secret; they stay out of the repository):
#   #!/bin/bash
#   dnf install -y -q git
#   git clone -q --depth 1 https://github.com/CodeGang007/telcron.git /opt/telcron/setup
#   API_HOST=<hostname> WEB_ORIGIN=<https://web host> bash /opt/telcron/setup/infra/aws/setup-backend-host.sh
# Output also goes to /var/log/telcron-setup.log (user-data has no terminal).
set -euo pipefail
: "${API_HOST:?}" "${WEB_ORIGIN:?}"
export HOME=${HOME:-/root}
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=/opt/telcron
COMPOSE_VERSION=${COMPOSE_VERSION:-v2.40.3}
BUILDX_VERSION=${BUILDX_VERSION:-v0.29.1}
mkdir -p "$ROOT"
exec > >(tee -a /var/log/telcron-setup.log) 2>&1
say() { printf '==> %s\n' "$*"; }

case "$(uname -m)" in
  aarch64) compose_arch=aarch64; buildx_arch=arm64 ;;
  x86_64)  compose_arch=x86_64;  buildx_arch=amd64 ;;
  *) echo "unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac

say "packages"
command -v dnf >/dev/null || { echo "expected Amazon Linux 2023 (dnf)" >&2; exit 1; }
# curl (curl-minimal), flock and python3 are part of the AMI.
dnf install -y -q docker git python3 >/dev/null
type -P aws >/dev/null || dnf install -y -q awscli-2 >/dev/null

say "docker"
# Container logs rotate, so they cannot fill the 20 GB disk.
if [ ! -f /etc/docker/daemon.json ]; then
  mkdir -p /etc/docker
  cat > /etc/docker/daemon.json <<'EOF'
{ "log-driver": "json-file", "log-opts": { "max-size": "10m", "max-file": "3" } }
EOF
fi
systemctl enable --now docker >/dev/null

# Amazon Linux's docker package has neither the compose nor (always) the buildx plugin. Pinned
# releases, checked against the published checksums.
plugins=/usr/local/lib/docker/cli-plugins
mkdir -p "$plugins"
fetch_plugin() { # fetch_plugin <url of binary> <url of checksums.txt> <asset name> <destination>
  local tmp
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/$3" "$1"
  curl -fsSL -o "$tmp/checksums.txt" "$2"
  (cd "$tmp" && grep -E "[ *]$3\$" checksums.txt | sha256sum -c --quiet -)
  install -m 755 "$tmp/$3" "$4"
  rm -rf "$tmp"
}
if ! docker compose version >/dev/null 2>&1; then
  base=https://github.com/docker/compose/releases/download/$COMPOSE_VERSION
  fetch_plugin "$base/docker-compose-linux-$compose_arch" "$base/checksums.txt" \
    "docker-compose-linux-$compose_arch" "$plugins/docker-compose"
fi
# Amazon Linux ships an old buildx (0.12) that compose build refuses (it needs 0.17 or later):
# install the pinned one unless what is there is new enough. /usr/local/lib wins over /usr/libexec.
buildx_ok() {
  local v
  v=$(docker buildx version 2>/dev/null | awk '{print $2}' | sed 's/^v//; s/-.*//')
  [ -n "$v" ] && [ "$(printf '%s\n' 0.17.0 "$v" | sort -V | head -1)" = 0.17.0 ]
}
if ! buildx_ok; then
  base=https://github.com/docker/buildx/releases/download/$BUILDX_VERSION
  fetch_plugin "$base/buildx-$BUILDX_VERSION.linux-$buildx_arch" "$base/checksums.txt" \
    "buildx-$BUILDX_VERSION.linux-$buildx_arch" "$plugins/docker-buildx"
fi
docker compose version
docker buildx version

say "swap"
# 2 GB of RAM is shared by PostgreSQL, the embedder, the API, the Worker and image builds.
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  [ -f /swapfile ] || { dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none; chmod 600 /swapfile; mkswap /swapfile >/dev/null; }
  swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap defaults 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/90-telcron.conf
sysctl -q -p /etc/sysctl.d/90-telcron.conf
swapon --show

say "settings"
# These identify the environment; none is a secret. They stay on the host, out of the repository.
umask 077
cat > "$ROOT/deploy.env" <<EOF
API_HOST=$API_HOST
WEB_ORIGIN=$WEB_ORIGIN
LOAD_SAMPLE=${LOAD_SAMPLE:-0}
APP_SECRET_ID=${APP_SECRET_ID:-telcron/dev/app}
AWS_REGION=${AWS_REGION:-us-east-2}
EOF
umask 022
install -m 755 "$HERE/agent-backend.sh" "$ROOT/agent-backend.sh"

say "deploy agent"
cat > /etc/systemd/system/telcron-deploy.service <<EOF
[Unit]
Description=Telcron: deploy the release branch if it moved
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
Environment=HOME=/root
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

say "nightly backup"
# The backup script runs from the deployed commit, so it follows releases like everything else.
cat > /etc/systemd/system/telcron-backup.service <<EOF
[Unit]
Description=Telcron: dump the database to S3
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
Environment=HOME=/root
EnvironmentFile=$ROOT/deploy.env
ExecStart=/usr/bin/bash $ROOT/repo/infra/aws/backup-db.sh
TimeoutStartSec=3600
EOF
cat > /etc/systemd/system/telcron-backup.timer <<EOF
[Unit]
Description=Telcron: database backup at 02:30 UTC

[Timer]
OnCalendar=*-*-* 02:30:00 UTC
Persistent=true
RandomizedDelaySec=5min

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now telcron-deploy.timer telcron-backup.timer
systemctl is-active telcron-deploy.timer telcron-backup.timer
say "done; the first deploy starts within a minute: journalctl -u telcron-deploy -f"
