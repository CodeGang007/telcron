# Week 2 · Sat 21 – Fri 27 Nov · Verify what exists, repair the board, M1 on dev

## Goal
Turn a week of fast building into a known, verified baseline. Nothing new is built until we know which of the fifteen work orders actually pass.

## Milestone
**M1 Foundation** — a new user signs up and verifies on dev; a scraping job fills `source_records` (tech doc §15.4).

## Starting point
Fifteen WOs, most DONE-PENDING-QA and never independently checked. The board contradicts the code in five places (PLAN §2.2). Sign-up is closed on the dev site. Four phase-two redemption items are on sale, two of which take coins and never complete.

## Work orders

- **WO-017 · Verification sweep** (`qa-test-engineer, browser-qa-engineer, security-auditor`): A verdict per WO-001…016 (PASS / FAIL with DEF-###). Every journey in `telcron-user-flows` walked on dev at 390 px and desktop. Security reviews of WO-002/016 (deployment), WO-013 (identity), WO-014 (research: injected pages, grounding).
- **WO-018 · Board and WO files repaired** (`tech-lead`): BOARD.md rows match the files and the code; WO-012 and WO-016 written after the fact; WO-005 and DEF-004 closed on QA's PASS.
- **WO-019 · Redemptions: phase-one items only** (`database-engineer, community-rewards-engineer`): Only the hazard report and extra watches active (D13); no code path leaves a redemption `processing`; a test redeems each active item and sees it fulfilled; any stuck redemptions on dev refunded through `coin_*`.
- **WO-020 · Dev hardening** (`infra-deploy-engineer`): DEF-006 closed (budget alarm notifies someone, Lightsail 22 closed or justified, app role not superuser, image not built on the small host); a dependency scan in the pipeline that fails on High.
- **WO-021 · M1 on dev** (`platform-identity-engineer, infra-deploy-engineer`): With the human's yes: sign-up open on the dev site; a new address receives the code, verifies, reaches Level 1; `hosted.spec.ts` covers it.
- **WO-022 · Phases 2–3 as migrations** (`database-engineer`): (If D11 = yes.) `dbmate up` on an empty database gives the same schema as today's dev; `make db-next` retired; drift test green.
- **WO-023 · Requirements traceability** (`requirements-analyst`): `docs/requirements/traceability.md` maps F1–F11 and the NFRs to WOs; `open-points.md` lists every contradiction and decision D1–D16.
- **WO-024 · Agent skills current** (`tech-lead`): The six skills and two agents on `feat/agents-and-skills` describe ADR-006/007 and the code as of this week; merged with the human's yes.

## Decisions due by the end of this week
D1 dates · D4 phone code (if reinstated, SMS sender registration starts this week, with cost) · D7 marketplace sources · D8 launch categories and countries · D11 migrations · D13 redemptions · D16 web app only.

## Performance plan
Baseline, not change: record cached-passport latency, search latency and `make db-test-perf` numbers on dev so later weeks are compared with something measured.

## Friday demo
The verification report (what passed, what didn't), a new user signing up on dev, the decisions list.

## The gate (Friday, before the demo)
The seven checks in `PLAN.md` §5, run and pasted into each WO's log: QA verdict with the revert proof ·
browser walk (phone width, reload, console, network, async loop) · security review where it applies · all
gates green and the pipeline green on `main` · performance targets for new reads · no stub called done ·
board, worklog and resume note updated.
