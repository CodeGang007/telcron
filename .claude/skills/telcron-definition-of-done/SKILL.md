---
name: telcron-definition-of-done
description: Telcron's Definition of Done — the gates every change passes before it can be called finished, with the exact commands. Load BEFORE reporting any work complete, before opening or closing a work order, and before any QA verdict.
---

# Definition of Done

Done is not "I wrote it". A change is done when every gate below has **actually been run and passed**, and a
different agent has verified it. A gate that did not run is `not run — <reason>`.

## Gate 0 — Scope
- [ ] The WO's `## Out of scope` is still true of the diff. Other bugs are under `### Flagged, not fixed`.

## Gate 1 — It conforms
```bash
make api-test                              # ruff: 0 findings, then the backend tests
cd frontend && npx tsc --noEmit            # 0 errors
```
A `# noqa` or `@ts-ignore` needs a reason on the same line.

## Gate 2 — Tests
```bash
make api-test      # needs `make up`; builds its own database from db/
make db-test       # after any change under db/ or docs/database/
```
- [ ] Every new branch of behaviour has a test, and the test goes red when the change is reverted.
- [ ] Access tests: no token (401), level or role too low (403), another user's row (404).
- [ ] Anything that awards or spends coins has a test that a repeat does not award twice.

## Gate 3 — It runs
- [ ] A change a member can see is covered by `cd e2e && npm run journey`, and that passes; `browser-qa-engineer`
      walked it (reload, phone width, console, network, the asynchronous loop).
- [ ] `make dev` starts API, Worker and web; the changed flow was walked in a browser, console clean.
- [ ] A schema change started in `schema_spec.py`, `make db-test` passes, and the drift test is green.
- [ ] `cd frontend && npm run build` succeeds for any frontend change.

## Gate 3b — It was reviewed
- [ ] A second agent reviewed the diff with `telcron-review-rubric`; no blocking finding open.
- [ ] Reads meet `telcron-performance`; rules match `telcron-business-rules` (or the open point is named).
- [ ] At a milestone, or for a multi-module change: `structure-auditor` PASS and a `code-quality-auditor` report.

## Gate 4 — It is safe
- [ ] No secret, token, code or ID document in a log, a response, a test fixture or the repository.
- [ ] `security-auditor` passed anything touching identity, sessions, roles, coins, uploads, the schema or AWS.

## Gate 5 — It is recorded
- [ ] WO log has the report block with real output. Board row updated. Status is `DONE-PENDING-QA`.
- [ ] A stub or unwired provider is reported as `PARTIAL` and named.


## Gate 6 — It is released
Merging to `main` deploys to dev. The work is not finished until the pipeline run for that commit is
green through its last step, `Check the live site`. A red `Release to dev` after green tests means the
code is on `main` and NOT live: say so, and look at the host's agent log (`docs/runbooks/aws-dev.md`).
