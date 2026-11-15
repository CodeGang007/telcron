# Agent workspace

How work moves through this repository. The behaviour is in the `telcron-agent-protocol` skill; this is the map.

| File | What it is | Who writes it |
| --- | --- | --- |
| `BOARD.md` | Everything in flight, one row each | `tech-lead` (engineers update their own row's status) |
| `work-orders/WO-###.md` | One owned piece of work, with its log | `tech-lead` opens; the owner logs |
| `contracts/CT-###.md` | A frozen API shape two owners build against | `tech-lead` |
| `defects/DEF-###.md` | Something wrong, with a repro | anyone; the finder does not fix |
| `WORKLOG.md` | Append-only long memory | `worklog-scribe` only |
| `RESUME-HERE.md` | Where to restart if a session died | whoever stops |
| `templates/` | Copy these; do not improvise the shape | — |

Statuses: `OPEN` → `DISPATCHED` → `DONE-PENDING-QA` or `PARTIAL` or `BLOCKED` / `BLOCKED ON HUMAN` → `DONE`
(set only by `tech-lead` after a different agent verified it). Decisions live in `docs/decisions/ADR-###-*.md`.
