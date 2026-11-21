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


## 2026-11-16 — Deployed to AWS dev; pipeline through main (WO-002, WO-009)

**Decided by the user**
- Deploy to AWS. Sign-up stays closed on the deployed site, with one seeded admin, until codes can be sent.
- Yes to: HTTPS on wildcard-DNS hostnames with Let's Encrypt; generated passwords in the app secret; the
  instance role reading the RDS master secret; fixed addresses; pushing the deploy files to `main`.
- Everything tested end to end, and an end-to-end CI/CD pipeline through `main`.
- The AWS CLI was installed for the user (no sudo); the user signed in with `aws login`. No keys exist.

**Done** — the dev site is live (WO-002). A push to `main` is tested and, if green, released to it without
anyone touching AWS (WO-009). The pipeline is pull-based because the account's policy denies the identity
provider GitHub would need; nothing was done to get around that.

**Not done** — security review of the deployment; DEF-006; the branch `release/dev` is unprotected; two
"Earn AWS credits" activities; everything else on the board.

Gates, 2026-11-16: pipeline run 43751927320 for commit f267b07 succeeded in all five jobs (schema tests, backend lint and tests, web typecheck and build, the member's journey in a browser, release to dev). After it both hosts reported f267b07 as the running build, without anyone touching AWS. Against the live site: the read-only smoke set passed 5 of 5, and the member journey signed in as the admin passed 5 of 5 steps (wallet round trip, a review re-screened from passport v1 to v2, earlier coins confirmed). Locally: make db-test 66 passed, make api-test 26 passed, journey 4 passed.


## 2026-11-21 — Moderation, recalls ingestion, scanning, AI scorer, evals, redesign

**Decided by the user**: stay on the AWS Free plan (so no Bedrock); no SerpApi/ScraperAPI, use free sources;
use a free model ("something like grok"): Groq's free plan chosen, not xAI (no free tier); redesign the UI with
open-source components, animation, logos, pagination; everything working end to end.

**Live** (commit c921389, all through the pipeline): safety-team review queue; CPSC recall ingestion (nightly +
admin) with 132 real notices imported on the dev site; barcode identification via UPCitemdb's free tier;
daily streaks, badges, coin store; the model scorer with stub fallback (switched off until a key exists);
`backend/evals` (12 cases) gating the pipeline at 90%; the redesigned web app.

**Found in Chrome, fixed**: newer Chrome returns a promise from `window.scrollTo`; an effect returned it and
crashed the app on every route change. The headless test browser did not have that behaviour, so the
pipeline did not catch it; the redesign build was live with it for one release (about 15 minutes).

**Honest caveat on evals**: the cases were written and the keyword placeholder tuned in the same session, so
its 97% is a regression baseline, not an independent quality measure.

**Open**: a Groq key to switch the AI scorer on; photo identification; media uploads; Level 2 identity; email/SMS
codes (sign-up still closed on the dev site).
