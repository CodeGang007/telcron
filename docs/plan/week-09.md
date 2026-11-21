# Week 9 · Sat 9 – Fri 15 Jan · Feature freeze: regression, load, security, replay rehearsal

## Goal
Prove it is ready. No new features from day one.

## Milestone
**M5 Release candidate** — the exit criteria of tech doc §14.1 met.

## Starting point
Feature complete in QA.

## Work orders

- **WO-046 · Regression in QA** (`everyone`): Every journey and every WO's criteria re-run on the release candidate; defects fixed by their owners.
- **WO-047 · Load test** (`infra-deploy-engineer, data-ai-engineer`): Passport reads, live screening and a full ingestion run against §3.2; results and bottlenecks recorded.
- **WO-048 · Security pass** (`security-auditor`): Requests that must be refused are refused; dependency scan clean; ID data deletion verified; secrets and roles reviewed.
- **WO-049 · Replay rehearsal; contract fixtures** (`data-ai-engineer`): A dead-letter replay rehearsed in QA; recorded fixtures for every provider in use.

## Decisions due by the end of this week
—

## Performance plan
This is the measurement week: the targets in PLAN §5 and tech doc §3.2, measured on QA.

## Friday demo
The release-candidate report against each exit criterion.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
