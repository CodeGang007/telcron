# Resume here

State at the end of the session of 2026-11-15. The detail is in `BOARD.md`; this is the short version.

## Where things stand
- `main`: the first application push. Its backend carries a provisional schema; do not build on it.
- `feat/database-schema` (the schema's author): the designed database. Untouched.
- `feat/backend-on-designed-schema`: `main` + that branch + the backend converged on it (WO-011).
  This is the branch to review and build on. It runs end to end locally; see `CLAUDE.md`.
- AWS dev hosts exist and are empty. Nothing is deployed. `docs/runbooks/aws-dev.md`.

## Waiting on the human
1. Review of `feat/backend-on-designed-schema` by the schema's author, then the merge into `main`.
2. Whether phases 2–3 become migrations (the backend needs them).
3. DEF-007: three gaps between what the backend wants and what the schema has.
4. The passport trust-score arithmetic (ADR-004).

## Named gaps in what is built
- Hazard scores come from `StubScorer`, a keyword placeholder. It is not AI.
- Recall matching uses identifiers and name similarity only; no vectors.
- Verification codes are shown on screen locally and never sent. There is no resend.
- A hazard flag can be filed but not confirmed; no API acts on the review queue.
- No ingestion, media, Level 2 identity check or business API.
- Nothing here has been verified by a second agent.

## Local machine notes
- Local source documents are under `docs/reference/` (gitignored).
- AWS identifiers are in `docs/runbooks/aws-dev.local.md` (gitignored).
- Settings, including the local admin password, are in `.env` (gitignored).
- The old `telcron-dev` Docker containers from the first schema are stopped and can be removed.
