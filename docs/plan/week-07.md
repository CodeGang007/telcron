# Week 7 · Sat 26 Dec – Fri 1 Jan · Level 2 identity (full week)

## Goal
Fully Verified members, with ID images that never outlive the match. Holiday week: two work orders only.

## Starting point
Level 2 is designed (WO-010) and blocked on D5.

## Work orders

- **WO-010 · Level 2 identity check** (`data-ai-engineer, platform-identity-engineer`): ID document read and selfie matched per D5; images deleted after the match (tested); result and score kept; +50 trust; failures counted for the alarm.
- **WO-041 · ID verification screens; phone code** (`frontend-engineer, platform-identity-engineer`): The Level 2 flow on a phone; clear failure states; if D4 = reinstate, phone code at Level 1 using the registered sender.

## Decisions due by the end of this week
—

## Performance plan
Identity work in the Worker; the member sees progress, not a spinner.

## Friday demo
A member reaching Level 2 (recorded if nobody is around on Friday).

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
