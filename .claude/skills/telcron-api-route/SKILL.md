---
name: telcron-api-route
description: How to add or change an API endpoint in Telcron — router, schemas, service, auth dependency, error codes, registration and tests. Load before writing or modifying any route.
---

# Adding a route

1. **Contract first** if another owner (usually frontend) consumes it: `CT-###` from the template, frozen by tech-lead.
2. `modules/<name>/schemas.py`: pydantic models with real bounds (`min_length`, `max_length`, `ge`, `le`, patterns).
3. `modules/<name>/service.py`: the logic. Raise `HTTPException(status, "snake_case_code")`; the code is the
   contract and the frontend maps it to a sentence.
4. `modules/<name>/router.py`: thin. Pick the caller from `core/deps.py`:
   `OptionalUser` (public), `CurrentUser`, `Level1User`, or `Depends(require_role("admin", "safety_reviewer"))`.
5. A new router is reported to `tech-lead`, who adds it to the list in `app/main.py`. All routes live under `/api/v1`.
6. A state change writes `audit(...)`. A change others must react to calls `emit(...)` in the same transaction.
7. Tests in `backend/tests/`: the happy path, each error status, the wrong verification level (403), no token
   (401), and another user's row (404).

## Status codes used here
`400` bad code or input the schema cannot express · `401` no or bad token · `403` level or role too low ·
`404` not found or not yours · `409` already exists or already done · `422` validation · `423` account locked.

Never return a provider's error text, a stack trace, or whether an email is registered (login and verify give
one answer for "unknown" and "wrong").
