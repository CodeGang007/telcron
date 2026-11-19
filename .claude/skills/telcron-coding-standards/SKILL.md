---
name: telcron-coding-standards
description: The coding standard every Telcron agent writes to — Python 3.13/FastAPI/async SQLAlchemy rules enforced by ruff, TypeScript strict and React rules for the web app, naming, error codes, logging, comments, the public-repository rule, and commit messages. Load before writing or reviewing code in backend/, frontend/ or e2e/.
---

# Coding standards

The repository enforces some of this (ruff, `tsc --strict`, the drift test); the rest a reviewer enforces with
`telcron-review-rubric`. When this file and the code disagree, the code's established pattern wins until an ADR
changes it — flag the disagreement, do not "fix" files you were not asked to touch.

## Enforced by the repo
- **ruff** (`backend/pyproject.toml`): line length 100, Python 3.13, rules `E F I UP B ASYNC S T20`.
  `S` catches hard-coded secrets and unsafe calls; `T20` forbids `print`; `ASYNC` forbids blocking calls in
  async code. A `# noqa: <code>` carries its reason on the same line.
- **TypeScript strict** (`frontend/tsconfig.json`); `npm run build` type-checks first. A `@ts-expect-error`
  carries its reason.
- **Drift**: `backend/app/models/` must match the database (`test_schema_drift.py`). Change
  `docs/database/schema_spec.py` first, never a model alone.

## Python (backend/)
- Type every function signature. Prefer `X | None` over `Optional[X]`; `uuid.UUID` for ids; `Decimal` for money,
  scores and confidences — never `float` for anything stored as `numeric`.
- Async all the way: `AsyncSession`, `await db.execute(select(...))`. No sync DB driver, no `requests`, no
  `time.sleep` in app code. Read-then-write on money or counters locks first (`.with_for_update()`).
- One transaction per request through the `Db` dependency. Do not `commit()` inside a service unless a rule
  says the write must survive a failure (the attempt counter on a wrong code does).
- Every list query has a `limit`, with a maximum on the endpoint. No unbounded `select`.
- Errors the client can act on: `raise HTTPException(status.HTTP_..., "snake_case_code")`. The code is stable
  API surface; add its sentence to `MESSAGES` in `frontend/src/lib/api.ts`. Never return a stack trace or a
  provider's raw error.
- Logging: `logging.getLogger("telcron.<area>")`. Log ids and outcomes, never tokens, codes, passwords, emails,
  phone numbers, ID-document data or full provider payloads.
- Pure rules with exact answers live in `app/domain/` with no I/O, so they unit-test without a database.
- pydantic v2 models for every request and response body (`schemas.py`); no raw dicts across a module boundary.
- Settings only through `core/config.py` (`get_settings()`); never `os.environ` in modules.

## TypeScript / React (frontend/, e2e/)
- No `any`; use `unknown` and narrow. Types for API responses live in `src/lib/api.ts` next to the calls.
- Every request goes through `src/lib/api.ts`. A page never calls `fetch`.
- No literal colours or ad-hoc spacing scales in components; tokens live in `src/index.css`. The look follows
  testlabhub.com.
- Every page handles loading, empty and error, and works at 390 px wide with no horizontal scroll.
- Function components and hooks only. No component file over 400 lines; split before it gets there.
- Accessible by default: real `<button>`/`<a>`, labels on inputs, alt text on product images, focus visible.

## Naming
- Python: `snake_case` functions and modules, `PascalCase` classes, `UPPER_CASE` constants. Event types are
  `PascalCase` past tense (`ReviewSubmitted`); queues are lower-case nouns (`screening`).
- Use the **schema's vocabulary** everywhere: `wallet_items`, `status_badge`, `near_match`, `not_checked` —
  never a synonym invented in code or UI copy. Feature ids `TC-P1-###`, work orders `WO-###`, defects `DEF-###`.
- TypeScript: `camelCase` variables, `PascalCase` components and types, one component per file named after it.

## Comments
Say **why**, not what: the rule, the decision (`ADR-00n`), the source (`TC-P1-016`, tech doc §9). No
commented-out code, no decorative banners, no `TODO` without a `WO-###` or `DEF-###`.

## The repository is public
No secret, credential, account id, resource id, IP address, hostname or database endpoint in a tracked file,
fixture or test. `.env` and `*.local.md` are gitignored. Source documents stay outside the repo.

## Commits
- Imperative, sentence case, describing the outcome: `Add the pipeline: tests on every push, release to dev
  from main`. One logical change per commit; never mix a refactor with a behaviour change.
- Reference the work order in the body when there is one. Committing locally needs no permission; **pushing
  does, and a push to `main` deploys to dev**.
