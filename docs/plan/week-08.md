# Week 8 · Sat 2 – Fri 8 Jan · Business API, second source, alarms, restore rehearsal

## Goal
Everything in scope exists and runs in QA. Feature freeze starts on Saturday.

## Milestone
**M4 Feature complete** — coins, Level 2, business API and two sources working in QA (tech doc §15.4).

## Starting point
Business tables from W5; Level 2 from W7; one marketplace source; metrics but no alarms.

## Work orders

- **WO-008 · Business API** (`platform-identity-engineer, frontend-engineer`): Keys for Level 2 accounts (hashed, shown once), rate limits, passport lookup, `POST /screenings`, signed webhooks on status change with retries, API documentation page.
- **WO-042 · Second source; price snapshots** (`data-ai-engineer, community-rewards-engineer`): Second marketplace source per D7; price snapshots stored so phase-two price alerts have history.
- **WO-043 · Alarms and dashboards** (`infra-deploy-engineer`): The alarms of tech doc §13 on the W6 metrics, each notifying a person; one dashboard; request tracing across API → queue → Worker → model.
- **WO-044 · Restore rehearsal** (`infra-deploy-engineer`): QA database restored from backup into a fresh instance, timed, written into the runbook.
- **WO-045 · Admin console complete** (`frontend-engineer`): Jobs, categories, users and roles, fraud holds, dead letters — each paginated and role-checked.

## Decisions due by the end of this week
—

## Performance plan
API keys rate-limited in Redis; webhook delivery in the Worker; passport lookup by key served from cache.

## Friday demo
A business key looking up a passport and receiving a webhook; two sources; an alarm firing.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
