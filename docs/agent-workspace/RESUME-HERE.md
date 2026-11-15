# Resume here

State at the end of the session of 2026-11-15. The detail is in `BOARD.md`; this is the short version.

## Where things stand
- `main` holds the application: backend, frontend, agents, skills, this workspace. It runs locally end
  to end (see `CLAUDE.md`).
- Branch `feat/database-schema` (another author) holds the designed database. It is not merged, and
  the backend's own schema disagrees with it on enum values. **WO-011 comes before anything else.**
- AWS dev hosts exist and are empty. Nothing is deployed. `docs/runbooks/aws-dev.md`.

## Waiting on the human
1. Schema: confirm `feat/database-schema` as the source of truth and who merges it.
2. AWS cost: keep RDS (about USD 33 a month) or move PostgreSQL onto the EC2 host (about USD 18).
3. Passport trust-score formula and reward level thresholds (ADR-004).

## Named gaps in what is built
- Hazard scores come from `StubScorer`, a keyword placeholder. It is not AI.
- Recall matching uses identifiers and name similarity only; no vectors.
- Verification codes are shown on screen locally and never sent. There is no resend.
- A hazard flag can be filed but not confirmed; no API acts on the review queue.
- No ingestion, media, Level 2 identity check or business API.
- WO-001 has not been verified by a second agent.

## Local machine notes
- Local source documents are under `docs/reference/` (gitignored).
- AWS identifiers are in `docs/runbooks/aws-dev.local.md` (gitignored).
- The local admin password is `SEED_ADMIN_PASSWORD` in `.env.local`.
