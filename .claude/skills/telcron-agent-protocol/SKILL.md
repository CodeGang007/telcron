---
name: telcron-agent-protocol
description: How Telcron's agents communicate — work orders, contracts, defects, decisions and the board in docs/agent-workspace. Load at the START of any multi-agent task, before dispatching or accepting work, and whenever you hand off, report back, file a defect or record a decision. Every agent in this repo loads this.
---

# Agent protocol

Agents here do not coordinate by chatting. They exchange file-backed artifacts under `docs/agent-workspace/`,
because **a subagent's context dies when it returns**. The board and the work orders are the working memory;
`WORKLOG.md` (written by `worklog-scribe` alone, append-only) is the long memory.

| Artifact | Where | Id |
| --- | --- | --- |
| Board | `BOARD.md` | — |
| Work order | `work-orders/WO-###.md` | `WO-001` |
| Contract (frozen API shape) | `contracts/CT-###.md` | `CT-001` |
| Defect | `defects/DEF-###.md` | `DEF-001` |
| Decision | `docs/decisions/ADR-###-slug.md` | `ADR-001` |
| Recovery note | `RESUME-HERE.md` | — |

## Before you do anything
1. Read `BOARD.md`. Two agents editing the same file in one pass is the failure this system prevents.
2. Read your work order end to end, including `## Out of scope`.
3. A contract your WO names is **frozen**. Disagreeing with it is a `BLOCKED` report, not a quiet change.
4. Load the skills your agent definition lists.

## While you work
- Append to your WO's `## Log` as you go. A run that dies halfway must still leave a usable trail.
- Cite `path/file.py:123`. Paste real output: `20 passed in 4.4s`, not "tests pass".
- The moment you need a file you do not own: stop, write `### Needs from another owner`, report.

## When you finish
Use `templates/report.md` verbatim, in the WO log and as your final message. The furthest you may move your own
item is **`DONE-PENDING-QA`**. Nobody marks their own work `DONE`.

## Proportionate verification
The full gate (separate QA agent, `security-auditor`) is for work touching identity, sessions, roles, coins, the
ledger, ID documents, the schema or AWS. A small change (copy, a style fix) gets the automated gates once, pasted
in the log, and that is the verdict.

## Honesty rules
- `PARTIAL` is respectable. A false `DONE-PENDING-QA` is not.
- Report what you did not do. Never silently widen or narrow scope; other bugs go under `### Flagged, not fixed`.
- A gate that did not run is "not run" with the reason. Never infer a result.
- A stub or an unwired provider is a named `PARTIAL`, never a `DONE`.
- **The finder does not fix.** File the defect and hand it to the owner.

## Asking the human
Investigate first. Escalate only when two readings produce materially different work and the code cannot settle
it, or the action is destructive, outward-facing or costs money (a push, a deploy, anything created or deleted in
AWS, any real email or SMS). Write it under `## Blocked on human`: the two readings, which you would pick and
why. Then carry on with whatever does not depend on the answer.
