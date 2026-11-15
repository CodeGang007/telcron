#!/usr/bin/env bash
# The web host's deploy agent. A systemd timer runs it every minute, as root.
#
# The pipeline on `main` builds the web app and commits it to the release branch under web/. This
# copies that build into place. It only ever copies static files: nothing from the repository is run.
set -euo pipefail

ROOT=/opt/telcron-web
REPO_URL=${REPO_URL:-https://github.com/CodeGang007/telcron.git}
BRANCH=${RELEASE_BRANCH:-release/dev}
SITE=/var/www/telcron
mkdir -p "$ROOT"

exec 9>"$ROOT/.deploy.lock"
flock -n 9 || exit 0

head=$(git ls-remote "$REPO_URL" "refs/heads/$BRANCH" | cut -f1)
[ -n "$head" ] || exit 0
[ "$head" = "$(cat "$ROOT/.release" 2>/dev/null || true)" ] && exit 0

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git clone -q --depth 1 --branch "$BRANCH" "$REPO_URL" "$tmp/release"
test -f "$tmp/release/web/index.html"

# Swap the directory in one move so a visitor never sees half a build.
rm -rf "$SITE.new" "$SITE.old"
cp -r "$tmp/release/web" "$SITE.new"
chown -R root:root "$SITE.new"
chmod -R a+rX "$SITE.new"
[ -d "$SITE" ] && mv "$SITE" "$SITE.old"
mv "$SITE.new" "$SITE"
rm -rf "$SITE.old"

echo "$head" > "$ROOT/.release"
echo "web release $head -> $(cat "$SITE/version.txt" 2>/dev/null || echo unknown)"
