# Week 10 · Sat 16 – Fri 22 Jan 2027 · Acceptance, production, launch ingestion, go-live, handover

## Goal
Telcron's users accept it, production is built once from the release candidate, and the team hands over.

## Milestone
**M6 Go-live** — production serving the launch categories.

## Starting point
Release candidate in QA, exit criteria met.

## Work orders

- **WO-050 · Production** (`infra-deploy-engineer`): Built per D2 with the human's yes and the cost; deployed once from the release candidate; smoke green.
- **WO-051 · Launch ingestion** (`data-ai-engineer, catalogue-engineer`): The three launch categories ingested and screened in production; counts and failures reported.
- **WO-052 · Acceptance and go-live** (`everyone`): Telcron's agreed scenarios passed in QA and signed off; go-live; first-day watch.
- **WO-053 · Handover** (`technical-writer`): Overview, API reference from the live OpenAPI document, admin guide, member help, release notes.

## Decisions due by the end of this week
—

## Performance plan
Production checked against the same targets on the first day.

## Friday demo
Live.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
