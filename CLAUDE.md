# MediSense AI — Claude Code Instructions

## Coverage Rules (non-negotiable)

- Run `cd backend && make cov` before every push. Every red line in the output is a line that will fail CI.
- Every new API endpoint must have tests **in the same commit** — no endpoint ships without coverage.
- `# pragma: no cover` is only for code that **cannot** be reached in a unit test:
  - ✓ External I/O adapter functions mocked at the call site in all tests (mark the `def` line, not individual lines inside the body)
  - ✓ Background fire-and-forget coroutines that tests always `close()` without awaiting
  - ✓ `if __name__ == "__main__":` guards
  - ✗ **NEVER** on a line an existing test already exercises — verify with `make cov` first
  - ✗ **NEVER** on individual lines inside a function body; mark the `def` line to exclude the whole body

## Endpoint Testing Contract

Every new FastAPI route requires tests for:
1. Happy path (200 or 201)
2. Auth/RBAC rejection — **HTTPBearer returns 403, not 401**, when the Authorization header is absent
3. Primary error path (404 / 409 / 422)

## Commit Discipline

- `make test` must pass locally before every `git push`
- A `fix(ci):` commit for something that `make test` would have caught locally is a process failure
- Stacked fix/cleanup commits on top of a feature delivery = the feature was not done

## CI / GitHub Actions

- `github.repository` → `owner/repo` — use for PR links and checkout refs
- `github.repository_owner` → `owner` — use for GHCR image names (nested path needs org permissions)
- GHCR image push requires `permissions: packages: write` on the job

## Tech Stack Quick Reference

- **DB writes**: `await db.flush()` inside endpoints, never `commit()` — the session middleware commits on clean response
- **Tests**: `asyncio_mode = auto`, real PostgreSQL 16 + Redis 7 via conftest fixtures, rolled back after each test
- **Coverage source**: `app/` only; `scripts/` and RAG/LLM adapters are excluded — see `backend/.coveragerc`
- **Auth tokens**: `create_access_token(subject=str(uuid.uuid4()), role="doctor"|"secretary"|"patient"|"admin")`
- **UUIDs in tests**: always use `str(uuid.uuid4())` for patient/doctor IDs passed to ORM or agent functions — never plain strings like `"patient-id"`

## Local Dev Workflow

```bash
cd backend
make install-hooks   # once per clone
make cov             # run before every push — shows red lines
make cov-html        # opens htmlcov/index.html for visual inspection
```
