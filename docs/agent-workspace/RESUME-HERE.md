# Resume here

State at the end of the run of 2026-11-22 (branch `week-02`, HEAD `7e1efd5`). Detail: `BOARD.md`, `WORKLOG.md`.

## Next step: the human's decisions and the push (not more building)
W1-W2 is built and verified by second agents (nothing is DONE; rows are DONE-PENDING-QA or lower). What is left
needs the human. A push to `main` is a release to AWS dev.

## Human actions
a. **Push `week-02` to `main`.** It is a release. WO-022's deploy-host change and the new migrations must go
   together. The S-19 network change restarts containers on the first deploy. Show what goes out first.
b. **DEF-040 key rotation**: Groq, Tavily, the Gmail app password, Gemini (from a Telcron project). $0.
c. **WO-021**: sign-up on dev; steps in `work-orders/WO-021.md` (after rotating the Gmail password and pushing). $0.
d. **DEF-006 items 1, 2, 4**: `## Blocked on human` in `work-orders/WO-020.md`. $0 each.
e. **DEF-045**: DB owner role. $0; needs database-engineer review.
f. **DEF-047**: backups versioning and lifecycle. About $0.00-0.05 per month.
g. **WO-054**: enable raw copies on dev. Under $0.05 per month.
h. **DEF-035**: choose reading (a) or (b) of D13 for the paid hazard report.
i. **DEF-046 / S-7r**: ADR on region and secret names in scripts and config.

Jira has not been updated (project-manager was not dispatched).

## Still open (not for the human alone)
DEF-110, DEF-111 (W3), DEF-007, DEF-002, DEF-024 (W4), D14 review by the schema's author, Gemini data-sharing
ADR, a partial unique index for DEF-032, `tools/dev-all.sh --no-proxy-headers`, Playwright headless browser not
installed locally, `.env.local` points the database at 5436.

## Where things stand
- `main` holds the teammate's work; `week-02` holds this run. Branch `release/dev` is written by the pipeline
  only; never push to it by hand.
- Named gaps: hazard scores use Groq with a stub fallback (`StubScorer` is not AI); WO-054 is PARTIAL until
  enabled on dev; WO-057's evals are a regression baseline, not an independent measure.

## Local machine notes
- Local source documents are under `docs/reference/` (gitignored).
- AWS identifiers are in `docs/runbooks/aws-dev.local.md` (gitignored); settings in `.env` (gitignored).
- The AWS CLI is at `~/aws-cli`; sign in with `aws login`.
