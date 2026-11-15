# Worklog

Append-only. Written by `worklog-scribe`. Newest entry last.

## 2026-11-15 — Foundation run (WO-001), AWS dev account, first push

**Decided by the user**
- Stack: React frontend, FastAPI backend. A TypeScript start made earlier the same day was deleted.
- UI follows testlabhub.com.
- Repository: first a private one under a personal account was chosen; later the user named
  `CodeGang007/telcron`, confirmed that its being public is fine, and said to push to `main`.
- AWS: Lightsail for the frontend, the smallest EC2 for the backend, PostgreSQL, Redis in Docker on the
  EC2 host. Target cost USD 20 to 22 a month.

**Built** — see WO-001 for the detail and the gate output.

**Found at push time**
- `CodeGang007/telcron` already had a branch, `feat/database-schema`, with the designed database:
  `schema_spec.py`, dbmate migrations, database-enforced rules, tests. The backend's schema had been
  built from the ERD pictures without it. Tables and columns match by name; 54 of 61 enum types have
  different values. Filed DEF-005 and WO-011. That branch was not touched or merged.
- That branch's `CLAUDE.md` says source documents live outside the repository. The local copies were
  therefore kept out of git (`docs/reference/`, gitignored).
- Because the repository is public: the seeded admin's password was moved out of the code into
  `SEED_ADMIN_PASSWORD`, the API now refuses the default `JWT_SECRET` outside local, and AWS
  identifiers are kept in a gitignored file.

**AWS dev, us-east-2** — inventory, cost and gaps in `docs/runbooks/aws-dev.md`. Created through
CloudShell in the console; no access keys were made. Four "Earn AWS credits" activities showed as
completed; the resources made only for them were deleted afterwards. The Bedrock activity could not be
done: the account's quota is zero.

**Open** — eleven work orders and six defects on the board; three decisions waiting on the human.

## 2026-11-15 — Converged on the designed schema (WO-011)

**Decided by the user**
- Rework the backend onto the schema of `feat/database-schema` on a new branch, for review.
- The AWS dev environment stays as built, about USD 33 a month ("its fine actually").
- Other local projects' dev servers were to be closed; Osten's were stopped with its own script.

**Done** on branch `feat/backend-on-designed-schema` — see WO-011 and ADR-005. The backend now creates
nothing: it maps the designed schema and a drift test guards the mapping. The database's rules replaced
the Python duplicates. Three faults surfaced and were fixed.

**Not done** — phases 2–3 are still not migrations; DEF-007 lists three gaps for the schema's author; the
two remaining "Earn AWS credits" activities (the browser chosen for it was not signed in to AWS).

## 2026-11-15 — Merged into main

At the user's instruction ("merge to main now") `feat/backend-on-designed-schema` was fast-forwarded into
`main`. That landed `feat/database-schema` as well. No pull request was opened; the schema's author has not
reviewed the convergence.
