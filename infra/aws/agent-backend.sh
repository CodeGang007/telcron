#!/usr/bin/env bash
# The backend host's deploy agent. A systemd timer runs it every minute, as root.
#
# It deploys whatever the release branch points at. That branch is advanced only by the pipeline on
# `main`, after every test has passed, and holds a VERSION file naming the commit to run. The host
# pulls; nothing outside can push to it, so GitHub holds no AWS credentials.
#
# Settings live in /opt/telcron/deploy.env (written once by setup-backend-host.sh):
#   API_HOST, WEB_ORIGIN, [LOAD_SAMPLE], [APP_SECRET_ID], [AWS_REGION], [REPO_URL], [RELEASE_BRANCH]
# A host whose deploy.env still names DB_HOST / RDS_SECRET_ARN is the pre-ADR-007 layout; the deploy
# script refuses to run there.
set -euo pipefail

ROOT=/opt/telcron
set -a
# shellcheck source=/dev/null
. "$ROOT/deploy.env"
set +a
REPO_URL=${REPO_URL:-https://github.com/CodeGang007/telcron.git}
BRANCH=${RELEASE_BRANCH:-release/dev}
RETRY_AFTER=600   # a release that failed to deploy is tried again after ten minutes, not every minute

exec 9>"$ROOT/.deploy.lock"
flock -n 9 || exit 0

head=$(git ls-remote "$REPO_URL" "refs/heads/$BRANCH" | cut -f1)
[ -n "$head" ] || exit 0
[ "$head" = "$(cat "$ROOT/.release" 2>/dev/null || true)" ] && exit 0
if [ "$head" = "$(cut -d' ' -f1 "$ROOT/.attempt" 2>/dev/null || true)" ]; then
  last=$(cut -d' ' -f2 "$ROOT/.attempt")
  [ $(( $(date +%s) - last )) -lt "$RETRY_AFTER" ] && exit 0
fi
echo "$head $(date +%s)" > "$ROOT/.attempt"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git clone -q --depth 1 --branch "$BRANCH" "$REPO_URL" "$tmp/release"
sha=$(tr -d '[:space:]' < "$tmp/release/VERSION")
case "$sha" in
  "" | *[!0-9a-f]*) echo "release $head has no usable VERSION" >&2; exit 1 ;;
esac
echo "release $head -> commit $sha"

# The deploy script comes from the commit being deployed, never from a copy left on the host.
[ -d "$ROOT/repo/.git" ] || git clone -q --depth 1 "$REPO_URL" "$ROOT/repo"
git -C "$ROOT/repo" fetch -q --depth 1 origin "$sha"
git -C "$ROOT/repo" show "FETCH_HEAD:infra/aws/deploy-host.sh" > "$tmp/deploy-host.sh"

GIT_REF=$sha bash "$tmp/deploy-host.sh"

echo "$head" > "$ROOT/.release"
rm -f "$ROOT/.attempt"
# Keep the agent itself in step with what was just deployed.
install -m 755 "$ROOT/repo/infra/aws/agent-backend.sh" "$ROOT/agent-backend.sh"
