# Week 6 · Sat 19 – Fri 25 Dec · Evidence loop; evaluation set; trust formula; metrics

## Goal
Prove the loop the product exists for, and measure the AI honestly. Short week: 25 Dec.

## Milestone
**M3 Evidence loop** — a review with a photo triggers a re-screen, a new passport version and an alert (tech doc §15.4), in QA.

## Starting point
Each part of the loop exists separately; the evaluation set was written by the same session that tuned it.

## Work orders

- **WO-037 · Evidence loop end to end** (`data-ai, community-rewards, frontend, browser-qa-engineer`): Review with photo → re-screen → new passport version → wallet owner alerted, walked in a browser on QA with timings.
- **WO-038 · Independent evaluation set** (`data-ai-engineer, requirements-analyst`): 20+ products from the launch categories with known recalls and labels, written by someone other than the prompt's author; accuracy per dimension reported against D10.
- **WO-039 · Trust-score formula** (`data-ai-engineer, database-engineer`): D9 implemented; `formula_version` moves off `provisional-0`; existing passports re-issued; alternatives use it.
- **WO-040 · Metrics for the alarms** (`data-ai, community-rewards, infra-deploy-engineer`): Emitted: uncited-score rate, image rejections, identity-check failures, cache hit ratio, fraud holds, daily AI spend, queue age, dead letters.

## Decisions due by the end of this week
D10 accuracy bar · D12 what leaves if W7 slips.

## Performance plan
The full loop measured end to end; screening p99 recorded.

## Friday demo
The loop live on QA. The evaluation report.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
