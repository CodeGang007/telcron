# WO-017 — QA part B verdicts (qa-test-engineer, run 2, 2026-11-22)

Tree: worktree `../wt-qa-b`, branch `wt/qa-b` = `week-02` @ `706b0f8`, plus one QA test commit `d9bd145`
(tests only). Lane: Postgres :55442, Redis :63842. No AWS call of any kind; no real provider key used
(`.env` has no `LLM_API_KEY`/`GEMINI_API_KEY`/`TAVILY_API_KEY`; evals run with them forced empty).

## Gates (run by me)
| Gate | Result |
|---|---|
| backend, 706b0f8 as is: `ruff check . && pytest -q` | `All checks passed!` · `83 passed, 4 warnings in 20.87s` |
| backend with the QA tests (d9bd145) | ruff clean · `93 passed in 15.34s` |
| schema: `pytest db/tests --ignore=db/tests/test_performance.py -q` | `66 passed in 3.19s` |
| `cd frontend && npx tsc --noEmit` | exit 0, no output |
| `npm run build`, `e2e journey` | not run — browser-qa-engineer's lane; no stack started in this lane |

Caveat: DEF-070 (data-ai-engineer) says `test_research.py` brand cases call the live CPSC registry
(`saferproducts.gov`, no key). My runs of that file may have done so; I did not add any network call.

## QA tests added (`d9bd145`, `backend/tests/`)
| File | Covers | Gap it closes |
|---|---|---|
| `test_qa_citations.py` | a scorer citing non-offered evidence → every dimension `insufficient_data`, no total, no citations | nothing failed when `service.py:287` was weakened (see WO-004) |
| `test_qa_resend.py` | resend after the minute issues a new code that verifies; old code dead; verified address gets nothing | only the refusal inside the minute was tested (see WO-013) |
| `test_qa_same_product.py` | two model numbers of one brand stay two products | only the positive match was tested (see WO-014) |
| `test_qa_access.py` | `POST /products/{slug}/research` 401 and 403; `/identify/photo` 403; research summary needs no account | no 401/403 on research, no 403 on photo |
| `test_qa_assistant_limits.py` | assistant daily cap → 429; search answers by name when the embedder is down | neither claim had a test (see WO-015) |

---

## WO-004 — Hazard scorer, vectors, photo identification — **PARTIAL** (confirmed)
| Criterion | Evidence | State |
|---|---|---|
| `BedrockScorer` behind `Scorer` | No Bedrock. `LlmScorer` (Groq, OpenAI-style; fallback model, then Gemini) wrapped by `FallbackScorer` → `StubScorer` on `httpx.HTTPError`/`ScorerError` (`screening/llm.py:174-213`); chosen only when `AI_PROVIDER=llm` and a key is set, else `StubScorer` (`scorer.py:101-106`) | PARTIAL by decision (D3) |
| Strict JSON, prompt version, tokens/cost in `ai_invocations` | `parse()` rejects unreadable answers, caps 0–100, drops unknown labels (`llm.py:150-172`); `AiInvocation` row with model, prompt version, tokens, latency, error (`service.py:274-278`); no cost column written | PASS except cost |
| Titan embeddings; pgvector recall retrieval | Superseded by WO-015's own embedder; recall candidates by `<=>` distance < 0.2, same brand (`service.py:63-69`) | SUPERSEDED / PASS |
| `POST /identify` from a photo | `POST /identify/photo` Level 1 (`catalogue/router.py:55`), vision model + Rekognition | PASS (security: DEF-024) |
| 20-product evaluation set | `evals/cases.json` has **12** cases. Offline run (stub): `answered by stub-heuristic-0: agreement 97% on 30 graded dimensions, citation validity 100%` (1 miss: prompt-injection / regulatory). The real model was not run (no key — by instruction). | PARTIAL |
| `StubScorer` is not shown as AI | `Product.tsx:214,335` "Keyword placeholder, not AI"; `Report.tsx:55` prints "Scored by stub-heuristic-0" (honest, but not labelled — nit) | PASS |

Revert proofs:
- `service.py:287` `score = result.score if (result and valid) else None` → `if result else None`: **the 83-test suite stayed green** (`83 passed in 16.20s`) — no test protected the non-negotiable. With `test_qa_citations.py`: red (`dimension safety.regulatory … is scored without a citation` — the database trigger also refuses), restored → `1 passed in 1.90s`.
- `llm.py:208` `except (httpx.HTTPError, ScorerError)` → `except ScorerError`: `FAILED test_a_failing_model_falls_back_to_the_stub_and_says_so` · restored `7 passed`.
- `llm.py:166` drop the `if c in labels` filter: `FAILED test_an_answer_is_mapped_back_and_bounded` · restored.

Verdict: **PARTIAL**, named: model scorer is Groq/Gemini free plans with `StubScorer` fallback (not Bedrock); eval set 12 of 20; cost not recorded. The board row is accurate. `make eval-research` without a key ends in a traceback (`ResearchUnavailable: no model configured`, nit); `make eval-assistant` without a key runs and reports "not configured".

## WO-013 — Sign-up codes by email; Level 1 = verified email — **PASS** (local code; live part not checked)
| Criterion | Evidence |
|---|---|
| `mailer.py` is the only file talking to email | `git grep smtplib\|sesv2` → only `modules/identity/mailer.py:8,39,52` |
| One email code; phone optional, not verified unless `LEVEL1_REQUIRES_PHONE` | `service.py:91-94`; `test_email_alone_reaches_level_1` |
| `POST /auth/resend`: once a minute, same answer for unknown address | `service.py:63-78`, `router.py:39-43`; `test_a_new_code_can_be_requested_once_a_minute`; new `test_qa_resend.py` |
| Refused send does not fail sign-up; `otp_failed` recorded; `otp_sent` only after acceptance | `service.py:47-60`; `test_a_refused_send_is_reported_and_not_logged_as_sent` |
| Migration relaxes `users_chk3` | `db/migrations/20261121120000_level1_email_only.sql`; `db/tests/test_identity.py:8`; schema suite 66 passed |
| Sign-up page: one code, "Send a new code", optional phone; sign-in asks for the code | `frontend/src/pages/Auth.tsx:86-102,154-194` |

Revert proofs (`tests/test_qa_resend.py` + the existing minute test):
- resend returns before issuing (`return None` before `_issue_code`): existing test **still passed**; `FAILED test_after_a_minute_resend_issues_a_new_code_that_verifies` · restored `3 passed`.
- gap check removed (`if False:`): `FAILED test_a_new_code_can_be_requested_once_a_minute`.
- refused send re-raised instead of `return False`: `FAILED test_the_code_is_emailed_and_a_refused_send_does_not_break_sign_up`, `FAILED test_a_refused_send_is_reported_and_not_logged_as_sent`. Restored: `7 passed`.

Not checked: the live site, Gmail SMTP delivery, SES (no AWS). The WO file's checklist items 6–8 are unticked though the work is merged (DEF-021). Identity security findings are security-auditor's (DEF-043 enumeration, DEF-044 rate limits, DEF-048).

## WO-014 — Research, photos, same-product matching — **PASS** (with DEF-024)
| Criterion | Evidence |
|---|---|
| Research module, run = ingestion job, cited `web_document` evidence, re-screen | `modules/research/{service,web,registries,router}.py`; `test_research_stores_cited_findings_and_rates_the_product` |
| Once a day per product; daily cap | `service.py:85-131` (`research_not_due`, `DAILY_CAP = 40`, real search balance). WO text says 15/day — changed by `23f8769` (nit: WO text stale) |
| Request needs Level 1 | `router.py:28`; new `test_qa_access.py` (401, 403) |
| Hallucination controls in code: numbered result only, injected pages dropped, brand named, grounded | `web.py:342-415`; `test_the_reader_keeps_only_findings_its_sources_say` |
| Photos: 1–4, private store, presigned 5 min | `PhotoIn` `max_length=4` (`router.py:41`), `photos.py:17,55`, 5 MB/image (`router.py:58`) |
| Same product: same brand + model, or ≥ 75 % core words; different model numbers never match | `identify.py:96,115-142`; `test_a_second_barcode_of_the_same_product_joins_it`; new `test_qa_same_product.py` |
| Hazard total ≥ 60 never "verified" | `domain/passport.py:22,73`; `test_a_high_hazard_score_is_never_verified` |

Revert proofs: injected filter removed (`web.py:355`) → `FAILED test_the_reader_keeps_only_findings_its_sources_say`; grounding off (`web.py:402`) → same test FAILED; per-product cooldown off (`service.py:121`) → `FAILED test_research_stores_cited_findings_and_rates_the_product`, `FAILED test_unread_pages_are_read_again_without_searching_again`; model-number guard off (`identify.py:137`) → `FAILED test_two_model_numbers_of_one_brand_are_two_products` (the existing positive test stayed green); `HIGH_HAZARD` 60→101 → `FAILED test_a_high_hazard_score_is_never_verified`; research route `Level1User`→`CurrentUser` → `FAILED test_asking_for_research_below_level_1_is_403`; photo route likewise → `FAILED test_identifying_from_a_photo_below_level_1_is_403`. All restored, `git status` clean.

Defect: **DEF-024** (S3, catalogue-engineer) — photos stored as sent; no server-side metadata strip or safety check. Research security (DEF-041, 042, 049) is security-auditor's. Evals with the real model not re-run (no key).

## WO-015 — Embedder, semantic search, alternatives, assistant — **PASS** (with DEF-022)
| Criterion | Evidence |
|---|---|
| Own embedder, one client file | `services/embedder/`; `modules/assistant/embedder.py` is the only caller of it |
| Schema spec-first, drift green | `test_schema_drift.py` in the 93-pass run |
| Search fuses names and meaning; falls back to names if the embedder is down | `catalogue/service.py:112-135`; `test_products_are_found_by_meaning_too`; new `test_search_still_answers_by_name_when_the_embedder_is_down` |
| Alternatives verified, trust ≥ floor, same kind, no demo products | `test_alternatives_are_verified_and_at_least_as_safe`, `test_alternatives_are_the_same_kind_and_never_demo_products` |
| Assistant: signed in; cites only offered labels; ungrounded → honest unknown; decline cites nothing; another member's thread 404; 40/day | `assistant/chat.py:37,84-90,140-207`; `test_the_assistant_answers_from_cited_evidence_and_remembers`; new `test_the_daily_question_limit_is_a_429` |

Revert proofs: citation filter removed (`chat.py:158`) → `FAILED test_the_assistant_answers_from_cited_evidence_and_remembers`; grounding off (`chat.py:165`) → same FAILED; owner check removed from the thread query (`chat.py:87`) → same FAILED (the 404 assertion); daily cap off (`chat.py:178`) → `FAILED test_the_daily_question_limit_is_a_429`; embedder failure not caught (`catalogue/service.py:119`) → `FAILED test_search_still_answers_by_name_when_the_embedder_is_down`. Restored.

Defect: **DEF-022** (S4) — malformed `thread_id` → unhandled `ValueError` (500). Not checked: the real embedder model, `make eval-assistant` with a model, the live deployment. WO-015's status line still says "deployment waits on WO-016" (DEF-021).

## WO-018 — Board and WO files repaired — **FAIL** → DEF-021 (S4, tech-lead)
Commit `50271d8` exists and did what its message says (BOARD, WO-004/005/013 status lines, WO-012/016 written, WO-021/024 opened). Rows WO-001…016 match their files' Status lines and cited commits exist (`a9002d2`, `067c961`, `772dc6e`, `4fe0649`, `3e588a0`, `2212f24`). Today's tech-lead changes to the WO-017/020/022/023/024 rows are expected and not counted. Mismatches: no `WO-018.md` at all; DEF-004 file `OPEN` vs board `FIXED-PENDING-QA`; WO-015 file "deployment waits on WO-016" vs board "live"; WO-013 checklist items 6–8 unticked vs "merged, live". No test applies; no revert proof.

## WO-024 — Skills and agents current — **FAIL** → DEF-020 (S3, tech-lead)
Acceptance greps over `.claude/skills/*/SKILL.md` and `.claude/agents/*.md` on 706b0f8:
- Phone for Level 1: **stale** — `telcron-user-flows/SKILL.md:31` ("email code, phone code, Level 1"; "codes are not sent anywhere yet (WO-005)"), `telcron-dev/SKILL.md:32` ("the two codes"), `agents/browser-qa-engineer.md:22` ("both codes"); also `CLAUDE.md:20` ("Level 1 needs verified email + phone"), changed by the same commit.
- RDS / t3.micro: clean (RDS only as "deleted 2026-11-21", `telcron-infrastructure/SKILL.md:22`; no `t3.micro`).
- Redemptions: clean (two phase-one items, `telcron-business-rules/SKILL.md:71-72`).
- `make db-next`: still in `telcron-db/SKILL.md:14`, `telcron-dev/SKILL.md:59-60`, `agents/database-engineer.md:22` — **expected, pending WO-022**, not failed.
- D7: recorded (`telcron-integrations/SKILL.md:31,44`, `agents/requirements-analyst.md:49`). D8: recorded (`telcron-integrations/SKILL.md:50`). **D16: recorded nowhere** (`grep -rniE "D16|phone-ready|native app" .claude/ CLAUDE.md` empty).
Nit: `2212f24` also edits `CLAUDE.md`, outside WO-024's stated scope. No test applies.

## WO-002 — Deploy dev to AWS (repository check only) — **PASS (repo)**, live criteria not checked
- `backend/Dockerfile:18,21` non-root user `telcron` (uid 10001). `infra/aws/deploy-host.sh:90,99` writes `ENV=dev`, `DEV_EXPOSE_CODES=false`; sample data only with `LOAD_SAMPLE=1` (`:141`); `config.py:92` refuses the default JWT secret outside local/test.
- The WO's RDS/ECR/Lightsail-nginx shape is superseded by WO-016 (one host, image built on the host — DEF-006). `docs/runbooks/aws-dev.md` describes the current shape; its "Known gaps" line 189-190 ("hazard scoring is still the keyword placeholder") is stale (nit, infra-deploy-engineer).
- Secrets scan of tracked files: no 12-digit account id, ARN, instance/sg/vpc/subnet id, access key, public IP or wildcard-DNS hostname (`git grep` patterns, only test barcodes and RFC test IPs matched); `git log -p --all` has no added line shaped like a Groq/Tavily/Google/AWS key. `.env` is untracked; only `.env.example` tracked. Names of resources and region appear in docs — security-auditor filed that (DEF-046); the runbook's leaked-keys note is DEF-040.
- Not checked (no AWS): `/health` over HTTPS, sign-up on the live site, the role reading secrets.

## WO-016 — Dev on one t4g.small (repository check only) — **PASS (repo)**, live criteria not checked
- Only Caddy publishes ports: `infra/aws/compose.yml:3,28-30` (80/443); postgres, redis, api, worker, embedder publish none.
- `telcron_app` NOSUPERUSER NOCREATEROLE NOCREATEDB (`deploy-host.sh:123-124`); it still owns the schema — DEF-045 (security-auditor).
- Nightly dump: `telcron-backup.timer` 02:30 UTC (`setup-backend-host.sh:139-155`), `backup-db.sh` dump → verify list → S3, prune > `KEEP_DAYS=14` (`backup-db.sh:16,30-49`); `restore-db.sh` exists (rehearsal is WO-044).
- No secret/id/address in tracked files: as in WO-002 (bucket named only as `telcron-dev-raw-<account-id>`; instance id points to `aws-dev.local.md`).
- Not checked: anything on the host.

## WO-005 — **SUPERSEDED** (claim true; may close)
Email codes and `POST /auth/resend` shipped in WO-013 and pass above (resend now proven to issue a working code). SMS is phase two (D4); no SMS client exists. The verify screen is reachable after leaving sign-up (sign-in asks for the code, `Auth.tsx:60-102`).

## WO-007 — **N/A, OPEN** (claim true)
No `review_media`/`hazard_flag_media` writes, no media queue handler, no perceptual hash computed. Note: WO-014 already writes `media_blobs` for product photos (`catalogue/identify.py:268`) without the safety check this WO plans (DEF-024).

## WO-008 — **N/A, BLOCKED ON HUMAN** (claim true)
No API-key or webhook model or route (DEF-002 open); `POST /screenings` exists (`screening/router.py:28`).

## WO-010 — **N/A, BLOCKED ON HUMAN** (claim true)
`IdentityVerification` is mapped (`models/identity.py:97`) but no `/auth/verify-id` route, no Textract, nothing writes the table.

## DEF-004 — **CLOSE**
The defect (no resend, no standalone verify) is fixed: `POST /auth/resend` (`identity/router.py:39-43`) proven by `test_a_new_code_can_be_requested_once_a_minute` and the new `test_after_a_minute_resend_issues_a_new_code_that_verifies` (revert proofs above); sign-in turns into the verify form on `email_not_verified` with "Send a new code" (`Auth.tsx:72,86-102`). The DEF file's own Status still says OPEN (DEF-021).

## Defects filed
| ID | Sev | Owner | Title |
|---|---|---|---|
| DEF-020 | S3 | tech-lead | Skills and agents still describe phone codes for Level 1; D16 recorded nowhere |
| DEF-021 | S4 | tech-lead | Board and WO files disagree after the WO-018 repair; WO-018 has no file |
| DEF-022 | S4 | data-ai-engineer (path unowned) | Assistant: malformed thread_id → unhandled ValueError (500) |
| DEF-023 | S4 | tech-lead | Domain map has no owner for research, assistant, moderation, evals, embedder, .claude/ |
| DEF-024 | S3 | catalogue-engineer | Member photos stored as sent: no server-side safety check or location-data removal |
