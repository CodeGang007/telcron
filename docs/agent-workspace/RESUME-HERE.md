# Resume here

State at the end of the session of 2026-11-16. The detail is in `BOARD.md`; this is the short version.

## Where things stand
- `main` holds everything and **a push to `main` is a release**: the pipeline tests it and, if green,
  deploys it to AWS dev by itself. Read `docs/runbooks/aws-dev.md` before changing the pipeline or `infra/`.
- The dev site is live. Its addresses are the repository's Actions variables `DEV_WEB_URL` and `DEV_API_URL`.
  Sign-up is closed there; one seeded admin signs in (password in the `telcron/dev/app` secret).
- Branch `release/dev` is written by the pipeline only. Never push to it by hand.

## Waiting on the human
1. A review, after the fact, by the schema's author of how the backend uses the schema.
2. Whether phases 2–3 become migrations (the backend needs them).
3. DEF-007: three gaps between what the backend wants and what the schema has.
4. The passport trust-score arithmetic (ADR-004).
5. Protecting `release/dev` and `main` (needs the repository's owner).

## Named gaps in what is built
- Hazard scores come from `StubScorer`, a keyword placeholder. It is not AI. Bedrock's quota is zero.
- Recall matching uses identifiers and name similarity only; no vectors.
- Verification codes are never sent; on the deployed site nobody can finish signing up.
- A hazard flag can be filed but not confirmed; no API acts on the review queue.
- No ingestion, media, Level 2 identity check or business API.
- DEF-006: four things to tighten in AWS dev. No monitoring, no alarms.
- Nothing here has been verified by a second agent.

## Local machine notes
- Local source documents are under `docs/reference/` (gitignored).
- AWS identifiers are in `docs/runbooks/aws-dev.local.md` (gitignored).
- Settings, including the local admin password, are in `.env` (gitignored).
- The AWS CLI is at `~/aws-cli`; sign in with `aws login`.
- The old `telcron-dev` Docker containers from the first schema are stopped and can be removed.
