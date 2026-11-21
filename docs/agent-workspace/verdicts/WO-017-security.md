# WO-017 — security review (security-auditor, 2026-11-22, `week-02` @ 706b0f8; main 067c961..23f8769)

Read-only review; no AWS call, no provider call, no gates run. Recorded by tech-lead from the auditor's report.
Overall: **SECURITY-PASS with findings** — no Critical, no High; five Medium to fix before WO-017 closes.

| Area | Verdict | Notes |
| --- | --- | --- |
| Deployment (WO-002, WO-016) | PASS-WITH-FINDINGS | Only Caddy publishes 80/443 (`infra/aws/compose.yml:27-30`); DB/Redis internal; local binds 127.0.0.1; pipeline holds no AWS credentials, write access only in the release job; secrets via stdin into umask-077 files. DEF-006 item 3 half done (`telcron_app` NOSUPERUSER, `deploy-host.sh:124`); items 1, 2, 4 open |
| Identity (WO-013) | PASS-WITH-FINDINGS | argon2; codes hashed, bound to user+purpose, 10 min, 5 tries; refresh rotation with family revoke on reuse; session-bound access tokens; lock after 5 bad passwords; Level 1 = verified email |
| Research (WO-014) | PASS-WITH-FINDINGS | No SSRF (Tavily snippets and fixed registry URLs only); injection: pattern filter, page text as data, citation by result number, 50 % overlap grounding; finding kinds whitelisted, lengths capped |
| Teammate's code (batched research, Gemini fallback, Tavily marketplace, `api-keys.md`) | PASS-WITH-FINDINGS | Keys from env/Secrets Manager only, in the Authorization header; never in a URL, log or response; history clean of keys, account ids, ARNs, registry hosts |

| Id | Sev | File:line | Issue | DEF |
| --- | --- | --- | --- | --- |
| S-1 | Medium | `docs/runbooks/api-keys.md:69-76` | Public file says provider keys leaked and are not rotated | DEF-040 |
| S-2 | Medium | `research/service.py:174,195-196`; `web.py:26-28,53-57` | Recall row carries the product's own name → guaranteed near-match | DEF-041 |
| S-3 | Medium | `research/router.py:39-46`; `market.py:73-110` | Anonymous GET calls Tavily + LLM in the API; drains allowance | DEF-042 |
| S-4 | Medium | `identity/service.py:83-84` | Register 409 reveals the account | DEF-043 |
| S-5 | Medium | `identity/router.py:275-315` | No rate limits on register/verify/resend/login | DEF-044 |
| S-6 | Medium | `infra/aws/deploy-host.sh:125,130` | Runtime role owns DB and tables | DEF-045 |
| S-7 | Low | `api-keys.md:5,37-38,40,60` (+ others) | Region and secret name in tracked files (the human's known finding) | DEF-046 |
| S-8 | Low | `backup-db.sh:21,40-48` | Host can delete its own backups | DEF-047 |
| S-9 | Low | `deploy-host.sh:156` | Seed admin password on a command line | DEF-047 |
| S-10 | Low | DEF-006 items 1, 2, 4 | Still open | DEF-006 |
| S-11 | Low | `pipeline.yml:28-30` | Actions pinned by tag | DEF-047 |
| S-12 | Low | `identity/service.py:178,183-184` | 423 on lock and timing reveal accounts | DEF-043 |
| S-13 | Low | `core/config.py:27,90-94` | `DEV_EXPOSE_CODES` not refused outside local/test | DEF-048 |
| S-14 | Low | `research/service.py:339,370`; `web.py:318` | Provider error text to anonymous callers | DEF-049 |
| S-15 | Low | `research/router.py:27-36,49-64` | No per-user research quota; market check trusts any title | DEF-049 |
| S-16 | Info | `identity/mailer.py:61`; `service.py:56` | Address logged; provider text in `auth_events`; product text goes to Gemini (ADR owed) | DEF-048 |
| S-17 | Info | `docs/database/db_erds.zip` (untracked); `aws-dev.md:152` | Zip not ignored (stays untracked by the human's instruction); field list lacks `GEMINI_API_KEY` | DEF-046 |

Not checked: anything live in AWS (security groups, IAM JSON, bucket settings, secret policy); GitHub branch
protection; restore/replay scripts beyond a skim; frontend rendering of external URLs (`rel`, scheme); Caddy's
X-Forwarded-For handling on the host; coin idempotency beyond the Level 1 award.

## Re-review, 2026-11-22, `week-02` @ d24b3b5 (diff 706b0f8..HEAD; uncommitted frontend ignored)
Overall **SECURITY-PASS with findings** (no S1/S2). WO-019 PASS · WO-022 PASS-WITH-FINDINGS (S-18) · DEF-011/012
PASS · DEF-043/044/048 PASS (private docker subnet acceptable in a public repo) · DEF-041/042/049/070 PASS ·
WO-054/WO-056 PASS · DEF-040/046/047 PASS-WITH-FINDINGS (S-7r).
Closed by evidence: S-2, S-3, S-4, S-5, S-9, S-11, S-12, S-13, S-14, S-15; S-1 text removed (rotation = human);
S-16 masked (Gemini ADR owed); S-17 field list fixed. Waiting on the human: S-6 (DEF-045), S-8, S-10 (DEF-006).

| Id | Sev | File:line | Issue | Owner |
| --- | --- | --- | --- | --- |
| S-18 | S3 | `db/migrations/20261122130200_phase3_schema.sql:786-830`, `…130000_phase2_schema.sql:342-361` | `dbmate rollback` drops the ledger, balances and redemptions even where the up-step was skipped (dev) | database-engineer |
| S-19 | S4 | `infra/aws/compose.yml:156-160` | No `ip_range`: Docker may give Caddy's pinned `.10` to another container first | infra-deploy-engineer |
| S-20 | S4 | `backend/app/modules/moderation/service.py:96-100` | Future task types not covered by the self-review check | community-rewards-engineer |
| S-21 | S4 | `backend/app/modules/research/service.py:123-127` | `research_per_user_per_day` read by `getattr`; no typed setting | platform-identity-engineer |
| S-7r | S4 | `deploy-host.sh:28`, `setup-backend-host.sh:105`, `core/config.py:96`, `RESUME-HERE.md:9`, `aws-dev.md` | Secret name, region, IAM role names still tracked (not credentials) | human (ADR) |
