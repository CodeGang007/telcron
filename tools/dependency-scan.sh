#!/usr/bin/env bash
# Known-vulnerability scan of every locked dependency. Fails on High or Critical; lower severities are
# printed and do not fail. Run by the pipeline on every push, before anything can be released, and by
# hand from the repository root:
#
#   tools/dependency-scan.sh              # all three: backend, frontend, e2e
#   tools/dependency-scan.sh python       # or: frontend, e2e
#
# Python: backend/uv.lock (all groups) is exported to a hashed requirements file and checked with
# pip-audit against the PyPA advisory database. pip-audit has no severity filter, so each finding's
# severity is looked up in OSV (the GitHub advisory's rating, via the finding's aliases). A finding
# whose severity cannot be determined counts as High: the scan fails closed.
# JavaScript: `npm audit --audit-level=high` over each package-lock.json (no install needed).
#
# Only package names and versions leave the machine (to PyPI's advisory service, OSV and the npm
# registry). Nothing here reads a secret.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PIP_AUDIT_VERSION=2.9.0
WHAT=${1:-all}
failed=0

python_scan() {
  echo "==> Python: ${REQUIREMENTS:-backend/uv.lock}"
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  if [ -n "${REQUIREMENTS:-}" ]; then
    # For testing the severity gate with a known-vulnerable file: REQUIREMENTS=path tools/dependency-scan.sh python
    cp "$REQUIREMENTS" "$tmp/requirements.txt"
    hashes=()
  else
    (cd "$ROOT/backend" && uv export --frozen --all-groups --no-emit-project -q -o "$tmp/requirements.txt")
    hashes=(--require-hashes)
  fi
  local rc=0
  uvx -q "pip-audit==$PIP_AUDIT_VERSION" -r "$tmp/requirements.txt" "${hashes[@]}" --no-deps --disable-pip \
    --progress-spinner off -f json -o "$tmp/audit.json" 2>"$tmp/audit.err" || rc=$?
  # pip-audit exits 1 when it finds something; anything else without a report is a broken scan.
  if [ ! -s "$tmp/audit.json" ]; then
    cat "$tmp/audit.err" >&2
    echo "pip-audit produced no report (exit $rc)" >&2
    return 1
  fi
  python3 -I - "$tmp/audit.json" <<'PY'
import json, sys, urllib.request

RANK = {"LOW": 1, "MODERATE": 2, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

def osv_severity(vuln_id):
    try:
        with urllib.request.urlopen(f"https://api.osv.dev/v1/vulns/{vuln_id}", timeout=20) as r:
            record = json.load(r)
    except Exception:
        return None
    sev = (record.get("database_specific") or {}).get("severity")
    return sev.upper() if isinstance(sev, str) and sev.upper() in RANK else None

report = json.load(open(sys.argv[1]))
deps = report["dependencies"] if isinstance(report, dict) else report
blocking = 0
found = 0
for dep in deps:
    for v in dep.get("vulns", []):
        found += 1
        ids = [v["id"], *v.get("aliases", [])]
        # The GitHub advisory carries the rating; PYSEC and CVE records usually do not.
        ids.sort(key=lambda i: not i.startswith("GHSA-"))
        ratings = [s for s in (osv_severity(i) for i in ids) if s]
        sev = max(ratings, key=RANK.get) if ratings else "UNKNOWN"
        blocks = sev == "UNKNOWN" or RANK[sev] >= RANK["HIGH"]
        blocking += blocks
        fix = ", ".join(v.get("fix_versions", [])) or "none yet"
        print(f"  {'BLOCK' if blocks else 'note '} {sev:<9} {dep['name']}=={dep['version']}  {v['id']}"
              f"  ({', '.join(v.get('aliases', [])) or 'no aliases'})  fixed in: {fix}")
print(f"  {len(deps)} packages, {found} known vulnerabilities, {blocking} High/Critical or unrated")
sys.exit(1 if blocking else 0)
PY
}

npm_scan() {
  local dir=$1
  echo "==> JavaScript: $dir/package-lock.json"
  (cd "$ROOT/$dir" && npm audit --audit-level=high)
}

case "$WHAT" in
  all) python_scan || failed=1; npm_scan frontend || failed=1; npm_scan e2e || failed=1 ;;
  python) python_scan || failed=1 ;;
  frontend|e2e) npm_scan "$WHAT" || failed=1 ;;
  *) echo "usage: $0 [all|python|frontend|e2e]" >&2; exit 2 ;;
esac

if [ "$failed" -ne 0 ]; then
  echo "dependency scan: High or Critical findings (or a broken scan) above" >&2
  exit 1
fi
echo "dependency scan: no High or Critical findings"
