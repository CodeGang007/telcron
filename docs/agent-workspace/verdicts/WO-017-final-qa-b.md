# WO-017 — Final QA, part B: board, docs, infra, web code (qa-test-engineer, 2026-11-22)

Tree: worktree `../wt-qa-final-b`, branch `wt/qa-final-b` = `week-02` @ `838beea`. No lane needed (no backend
or schema suite in part B). No AWS call, no push, no workflow dispatch. The worktree's only untracked entry,
`frontend/node_modules` (a symlink to the main tree's, created before this run), was used for tsc/build and left
in place; everything I changed in the worktree was restored (`git status --short` → only that entry).

## Gates run by me
| Gate | Result |
| --- | --- |
| `cd frontend && npx tsc --noEmit` | exit 0, no output |
| `cd frontend && npm run build` | `✓ built in 5.52s` (exit 0; the usual >500 kB chunk warning for `index` and `Scan`) |
| `tools/dependency-scan.sh` (all) | Python `52 packages, 0 known vulnerabilities, 0 High/Critical or unrated` · frontend `found 0 vulnerabilities` · e2e `found 0 vulnerabilities` · `dependency scan: no High or Critical findings`, exit 0 (8.8 s) |
| pipeline YAML | `yaml.safe_load` OK; jobs `deps, schema, backend, frontend, e2e, release` |
| `bash -n infra/aws/*.sh` | all 9 ok |
| `docker compose -f infra/aws/compose.yml config -q` (dummy env) | OK |

## Verdicts
| Item | Verdict |
| --- | --- |
| WO-018 | **FAIL** → DEF-090 (S4, tech-lead) |
| DEF-021 | PASS |
| WO-024 | PASS |
| DEF-020 | PASS |
| DEF-023 | PASS (nit: some paths still unowned) |
| WO-020 (scan, gating, SHA pins, YAML) | PASS |
| DEF-040 (runbook part) | PASS — key rotation itself remains with the human |
| DEF-046 (runbook part) | PASS — scripts/config/skill decision remains with the human |
| DEF-047 (S-9, S-11) | PASS — S-8 backups remain with the human |
| DEF-044 infra + S-19 | PASS (repo; not verified live) |
| WO-022 infra follow-up | PASS |
| WO-055 admin shell | PASS (code review) — browser walk not done by me |
| WO-056 flags hook | PASS (code review against CT-001) |
| DEF-013 | PASS |
| DEF-014, 030, 031, 033, 034, 036, 037, 038 | PASS (code review) — behaviour in the browser not checked by me |
| Public-repo scan | PASS (region/secret *names* remain outside runbooks, already DEF-046's open decision) |
| `db_erds.zip`, `aws-dev.local.md` untracked | PASS |

---

## WO-018 — Board and WO files repaired — FAIL → DEF-090
- DEF-021's four points are fixed: `work-orders/WO-018.md` exists; `defects/DEF-004.md:4` "CLOSED 2026-11-22" =
  board "CLOSED"; `WO-015.md:4` "live on dev since WO-016" = board "live"; `WO-013.md:58` tech-lead note marks the
  checklist historical (items 6–8 still unticked, explained).
- Acceptance 1 ("each file's status line agrees with its row") is false again for 15 rows: WO-019/020/022/023/
  054/055/056/057 header lines say OPEN/DISPATCHED while the board says DONE-PENDING-QA/PARTIAL; DEF-030/031/033/
  034/036/037/038 files say FIXED-PENDING-QA while the board says "OPEN — fixing"; DEF-024 OPEN vs RESCHEDULED.
  Full table and repro in `defects/DEF-090.md`. S4 bookkeeping; no code impact.

## DEF-021 — PASS
As above (points 1–4 each checked against the file).

## WO-024 / DEF-020 — PASS
```
$ grep -niE "phone code|two codes|both codes" .claude/skills/*/SKILL.md .claude/agents/*.md CLAUDE.md
business-rules:25  "... Phone codes are phase two (LEVEL1_REQUIRES_PHONE, off)"
integrations:70    "| SMS | phone codes | — | phase two (D4) |"
CLAUDE.md:20       "Level 1 needs a verified email (ADR-006; phone code is phase two, D4)."
user-flows:34      "Level 1 = verified email (ADR-006, D4: no phone code in phase one)"
$ grep -rniE "D16|phone-ready|native app" .claude/ CLAUDE.md
.claude/skills/telcron-user-flows/SKILL.md:27: Platform (D16): a phone-ready web app only; native apps are phase two. ...
```
Every hit now says phone is phase two. `telcron-dev/SKILL.md:32` and `browser-qa-engineer.md:22` say "the email
code". Other WO-024 lines: RDS only as "RDS deleted 2026-11-21"; no `t3.micro`; `make db-next` only as "retired"
(`telcron-db/SKILL.md:14`); no `schema-next` in `.claude/` or `CLAUDE.md`; redemption phase one = two items
(`business-rules:71`); D7 (`integrations:31,44`, `user-flows:41`), D8 (`integrations:50`, `user-flows:27`).
The stale journey-table entries DEF-020 named ("only StubScorer", "waits for vectors", "codes are not sent") are gone.

## DEF-023 — PASS
`.claude/skills/telcron-domain-map/SKILL.md:15` gives data-ai-engineer `modules/ingestion/**`,
`modules/research/**`, `modules/assistant/**`, `backend/evals/**`, `services/embedder/**`; `:16`
community-rewards-engineer `modules/moderation/**`; `:20` tech-lead `.claude/**`. All ten `backend/app/modules/*`
are in the table, each once.
Nit (not filed): still no owner for `Makefile`, `README.md`, `.env.example`, `.gitignore`, `backend/Dockerfile`,
`backend/pyproject.toml`, `backend/app/seed.py`, `backend/app/domain/trust.py`, `e2e/`'s non-test files; and
`docs/agent-workspace/**` (tech-lead) overlaps `WORKLOG.md` (worklog-scribe) and the verdicts (qa).

## WO-020 — dependency scan — PASS
- Clean run: see Gates (Python 52 packages / 0 vulns; npm 0 and 0).
- Fails on a known-vulnerable pin (worktree, then restored with `git checkout`):
  - Python: `uv add "urllib3==1.26.4" --no-sync` (real `uv.lock` path, hashes on) → `tools/dependency-scan.sh python`:
    ```
    BLOCK HIGH      urllib3==1.26.4  PYSEC-2023-192  (GHSA-v845-jxx5-vc9f, CVE-2023-43804)  fixed in: 1.26.17, 2.0.6
    ...
    52 packages, 11 known vulnerabilities (8 high, 3 moderate), 8 High/Critical or unrated
    dependency scan: High or Critical findings (or a broken scan) above
    EXIT 1
    ```
  - JavaScript: `npm install lodash@4.17.11 --package-lock-only` in `e2e/` → `tools/dependency-scan.sh e2e` →
    `1 critical severity vulnerability` … `EXIT 1`.
  - Restored: `git status --short` → only the pre-existing `frontend/node_modules` symlink.
- Gating: `.github/workflows/pipeline.yml:21-35` job `deps` runs `tools/dependency-scan.sh`; `release`
  `needs: [deps, schema, backend, frontend, e2e]` and runs only on push to `main`.
- SHA pins (DEF-047 S-11): all 15 `uses:` lines are 40-hex SHAs with the tag in a comment (checkout
  `11d5960…` v4.4.0, setup-uv `d0cc045…` v6.8.0, setup-node `49933ea…` v4.4.0, upload-artifact `ea165f8…` v4.6.2).
  `permissions: contents: read` at top; `contents: write` only on `release`.
- Not run: the pipeline itself (needs a push).

## DEF-040 — runbook part PASS
`git grep -niE "rotate when convenient|borrowed|shared in a chat|leaked|not yet rotated|current status" -- docs/runbooks`
→ only `api-keys.md:71-72`, the generic "When a key leaks" how-to ("Track a leaked key in a defect, never in
this file"). No statement about any individual key. Rotation: BLOCKED ON HUMAN as the DEF says (the old text
remains in git history; only rotation closes it).

## DEF-046 — runbook part PASS
`git grep -nE "<real region>|<real secret name>" -- docs/runbooks` (values read from the gitignored
`aws-dev.local.md`, not repeated here) → no output, rc 1. Placeholders in use: `api-keys.md` 5 lines,
`aws-dev.md` 6 lines; `aws-dev.md:164` lists `GEMINI_API_KEY` (S-17). The same names remain in
`infra/aws/{deploy-host,db-lib,setup-backend-host,migrate-from-rds}.sh`, `backend/app/core/config.py`,
`.claude/skills/telcron-infrastructure/SKILL.md` and some workspace docs (WORKLOG, RESUME-HERE, WO-004, WO-013):
names, not ids — this is the open A/B decision recorded in DEF-046, not a new defect.

## DEF-047 — S-9, S-11 PASS
- `infra/aws/deploy-host.sh:151`
  `SEED_ADMIN_PASSWORD="$SEED_ADMIN_PASSWORD" compose run --rm -T -e SEED_ADMIN_PASSWORD api python -m app.seed`
  — the command line carries the name only. No other `-e NAME=value` with a secret in `infra/aws/*.sh`
  (only `db-lib.sh:30 -e AWS_DEFAULT_REGION=…`, not a secret). `bash -n` ok on all nine scripts.
- S-11: see WO-020.
- S-8 (backups): PREPARED, BLOCKED ON HUMAN — not checked further.

## DEF-044 infra + S-19 — PASS (repo)
- `backend/Dockerfile:28` `CMD [... "--no-proxy-headers"]`; no `--proxy-headers`/`--forwarded-allow-ips`
  anywhere in `backend/Dockerfile`, `Makefile`, `docker-compose.yml`, `infra/`, `tools/`, `.github/`. The locked
  uvicorn (0.54.0) lists `--proxy-headers / --no-proxy-headers` in `--help`.
- `infra/aws/compose.yml`: network `app` `subnet: 172.30.250.0/24`, `ip_range: 172.30.250.128/25` (dynamic
  addresses only in the upper half); `caddy` `ipv4_address: 172.30.250.10`; `TRUSTED_PROXIES: 172.30.250.10/32`
  in the shared `x-backend` env (api, worker). Every service is on `app`; only Caddy publishes ports.
  `backend/app/core/ratelimit.py:50` reads `trusted_proxies`. `compose config -q` OK.
- Not verified live (takes effect on the next release).
- Still flagged by the fixer, not filed by me: `tools/dev-all.sh` runs uvicorn with defaults (local only).

## WO-022 infra follow-up — PASS
`git grep -n "schema-next" -- infra .github tools docs/runbooks Makefile` → nothing (rc 1). `db/schema-next/` does
not exist. `Makefile:69-70` keeps `db-next` only as a retired stub that prints "run make db-migrate".
`infra/aws/deploy-host.sh:129-135`: `say "migrations"` → `compose run --rm -T migrate up`, then
`say "reference data"` → `pg telcron_app -f /db/seeds/001_core_reference.sql` (migrate before reference data;
phases 2–3 reference rows are in migration `20261122130400_phase2_3_reference.sql`).

## WO-055 — admin shell — PASS (code review)
- `frontend/src/pages/admin/AdminLayout.tsx`: loading → skeleton; no `me` → "Sign in to continue"; non-staff →
  `NotFound` (no admin chrome); moderator on an admin-only section (`SECTIONS` roles) → `NotFound`. Tabs scroll
  horizontally under `lg`, side list at `lg`; nested `Suspense` around `Outlet`.
- `sections.ts`: Overview (admin, moderator), Data sources (admin), Review queue (admin, moderator).
  `AdminHome.tsx`: one card per allowed section, no figures.
- `main.tsx:52,54` redirect `/review-queue`, `/data-sources` → `/admin/...` (`replace`); `:55-58` nested routes;
  `/admin/<unknown>` falls through to `*` → NotFound. `Layout.tsx:58,89` account menu → `/admin` for staff.
- Tokens only (DEF-013 grep clean). Backend still enforces roles on the APIs, so the shell is presentation only.
- Not checked by me: 390 px / desktop, reload keeps the section, console — browser-qa-engineer's lane.
- Nit: WO-055.md header still says `Status: OPEN` (in DEF-090).

## WO-056 — flags hook — PASS (code review against CT-001)
`frontend/src/lib/flags.ts`: one `GET /flags` per load through `api()` (shared module-level promise); keeps only
`true` values from `{"flags": {...}}`; `useFlag(code)` false while loading, on error (failure → `{}`) and when
absent — matches CT-001 "absent = off". Server side (`backend/app/core/flags.py`) answers the CT-001 shape with
`Cache-Control: public, max-age=60` and is registered (`main.py:12,47`); its tests are part A's.

## DEF-013 — PASS
The Fix's grep, run in `frontend/src` over `*.tsx`/`*.ts` → no output (rc 1). An extra grep for arbitrary values
(`[#…]`, `[rgb…]`, `oklch(`, named colours in `style`) → nothing.

## DEF-014 — PASS (code review)
`frontend/src/lib/usePaged.ts`: depth stored per `location.key` + path in sessionStorage after each "show more";
on mount reloads that many (chunks of 50, cap 200), stale responses dropped by a generation counter.
Not checked: the reload walk in a browser.

## DEF-030 — PASS (code review)
`pages/Product.tsx:116-124` reads `/wallet/items` for Level 1 and sets "In your wallet" when slug or id matches
(`wallet/router.py:29` returns both); `:159` 409 `already_in_wallet` flips the button.

## DEF-031 — PASS (code review)
`components/Reviews.tsx`: "Helpful" (`min-h-11`) on others' reviews; author/own → count only; visitor "Sign in to
vote helpful", below Level 1 "Confirm your email…"; `review.voted`/`review.mine` from the API (back half, part A's).
Nit: the comment at `Reviews.tsx:17-18` says the list "does not say yet whether the caller voted" — it does now;
the localStorage fallback is redundant.

## DEF-033 — PASS (code review)
`pages/DataSources.tsx:142-143` two lists "Recall imports" / "Product research runs"; `:34` research triggers in
words; `:79` links the product by id (the API accepts `id_or_slug`); `:42,59,88` errors as sentences.

## DEF-034 — PASS (code review)
`lib/coins.ts` event; fired after a redemption (`Rewards.tsx:294`) and a review (`Reviews.tsx:132`);
`lib/auth.tsx:42-45` reloads `/auth/me` on it and on tab visible; `Layout.tsx:45-48` re-reads `/coins` on `me`.
A 5xx/network failure of `/auth/me` no longer signs out (`auth.tsx:26-28`).

## DEF-036 — PASS (code review)
`lib/useLoad.ts` `notFound` only on 404; `Product.tsx:128-139` 404 → "We could not find that product", else
"This product could not be loaded" + Try again; `Search.tsx:24` empty state only when no error;
`api.ts:135,146` network / 5xx messages.

## DEF-037 — PASS (code review)
`components/PassportPreview.tsx` draws the hero from a real product's current passport (version, badge, trust,
recall count, hazard label, scored dimensions, `verified_at` date); nothing when no product is screened.
Nits: (1) with only demo products it picks a demo product without an "Example"/demo marker; (2) the chip
"+25 TelCoins for a confirmed hazard report" is a constant — it matches `hazard_flag_confirmed` = 25
(`db/migrations/20261122130400_phase2_3_reference.sql:48`) today, but would drift if the table changes.

## DEF-038 — PASS (code review)
`pages/Wallet.tsx:44-47` Remove always visible, `size-11` (44 px), labelled "Remove <name> from your wallet";
`:83` toast with Undo for 8 s; no `window.confirm`.

## Public repository — PASS
Over `git ls-files` (lockfiles excluded where noted):
- 12-digit numbers: only barcodes (tests, fixtures, demo seed, e2e), a placeholder phone in `Auth.tsx:170`. No account id.
- ARNs: only the placeholder `arn:aws:s3:::<raw bucket>` in `DEF-047.md:67`.
- Public IPv4 outside private/documentation ranges: only test values in `backend/tests/test_identity_hardening.py:167,169`,
  `db/tests/test_identity.py:78,91` (1.2.3.4, 8.8.8.8, 9.9.9.9) and `DEF-044.md:33` (6.6.6.6, a spoof example). No
  host address. (Nit: TEST-NET ranges would be cleaner.)
- Hostnames: URLs are public sources/providers, `example.*`, `localhost`; no Telcron host, no `amazonaws.com`,
  no instance/VPC/SG/subnet/AMI ids.
- Key-shaped strings (AWS AKIA/ASIA, `gsk_`, `tvly-`, `AIza`, `sk-`, GitHub tokens, private keys, JWTs, 64-hex):
  none. Only the documented default `JWT_SECRET=change-me…` (`.env.example:20`, `config.py:8`, refused outside local/test).
- `docs/runbooks/aws-dev.local.md`: not tracked, ignored by `.gitignore:40:*.local.md`.
- `docs/database/db_erds.zip`: not tracked (`git ls-files` → nothing) but **not ignored** either (shows `??` in
  the main tree) — one `git add -A` would commit it. Nit for tech-lead/database-engineer.

## Not checked
- Browser behaviour of WO-055 and every frontend DEF (390 px, reload, console, network): browser-qa-engineer.
- Backend suites (part A), live dev site, the pipeline run itself, anything on AWS.

## Good
- The dependency scan fails closed (unrated or OSV unreachable counts as High) and uses the real hashed lockfile.
- The proxy fix removes the double application cleanly: uvicorn trusts nothing, the app trusts exactly Caddy's
  pinned address, and `ip_range` makes the pin safe.
