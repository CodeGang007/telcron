---
name: telcron-review-rubric
description: How to review a Telcron change — the standard of approval, what to check in order (the database's rules and business rules, security and privacy, data integrity, tests, ownership and architecture, performance, readability), what blocks a merge versus what is a nit, and the verdict format. Load before reviewing any diff, before a QA or audit verdict, and before approving your own plan for a change.
---

# Review rubric

**Approve when the change leaves Telcron healthier than it found it** — not when it is perfect. Block only for
what would hurt a person, the data or the next engineer. Everything else is a nit: say it once, move on.

Load with it: `telcron-business-rules`, `telcron-coding-standards`, `telcron-testing`, `telcron-architecture`.

## What to check, in this order
1. **Scope.** Does the diff do what the work order says, and only that? Unrelated changes are their own WO.
2. **Rules.** Does any write fight the database (trigger, CHECK, `coin_*`, append-only) instead of satisfying
   it? Does every number come from its table, not a constant? Does the behaviour match
   `telcron-business-rules` — and where a rule is "Open", is the assumption stated?
3. **Honesty of what users see.** Could this make a passport look safer than the evidence says: an uncited
   score shown as zero, `not_checked` shown as "not certified", "no match" without its date, a stub's output
   shown as AI?
4. **Security and privacy** (`telcron-security`). Level and role checked on the route; another user's row a
   404; no secret, token, code, ID-document data or personal data in logs, responses, fixtures or the repo; input
   validated; provider output treated as data.
5. **Money and idempotency.** Coins awarded or spent only through `coin_*`, once per idempotency key.
6. **Tests** (`telcron-testing`). New behaviour has a test that goes red on revert; access tests present; the
   async path asserted; real gate output pasted.
7. **Ownership and architecture.** One owner's paths (`telcron-domain-map`); thin router; logic in the service
   or `domain/`; outside calls only in a provider client in the Worker; events routed in `ROUTES`.
8. **Performance** (`telcron-performance`). Bounded queries, the right index, no N+1, slow work in the Worker.
9. **Readability.** Names from the schema's vocabulary, comments that say why, no dead code.

## Blocks
- Breaks a database rule or works around it; writes coins or an append-only table directly.
- A user could see another user's data, or a misleading passport.
- A secret, credential or identifier enters a tracked file.
- New behaviour without a test, or a test that does not fail on revert.
- A gate reported as passing that was not run.
- A provider called outside its client, or a real provider called from a test.
- Touches identity, sessions, roles, coins, the ledger, ID documents, uploads, the schema or AWS without
  `security-auditor`.
- Edits another owner's file without a frozen contract.

## Nits — mention, do not block
Naming that could be clearer, a missing comment on a non-obvious line, a test name, ordering of imports the
linter allows, a small duplication that has one caller today.

## Say what is good
Name one or two things done well, specifically. It tells the author what to keep doing.

## Verdict
```
## Review: WO-### — <commit or branch>
Verdict: APPROVE | APPROVE WITH NITS | REQUEST CHANGES
### Blocking
1. <claim> — path/file.py:NN — <why it hurts, which rule>
### Nits
- <claim> — path:NN
### Good
- <specific>
### Not checked
- <what and why>
```
