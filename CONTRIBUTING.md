# Contributing to MediSense AI

## Local Setup

```bash
# Clone and install
cd backend
pip install -r requirements.txt

# Install the pre-push hook (one-time per clone)
make install-hooks
```

The pre-push hook runs `pytest --cov=app --cov-fail-under=80` before every `git push`. It blocks the push on failure. Use `git push --no-verify` only in genuine emergencies.

---

## Definition of Done

Every PR must satisfy **all** of these before merge:

- [ ] `make test` passes locally — all tests green, coverage ≥ 80%
- [ ] `make cov` shows no uncovered lines in new or changed files
- [ ] Every new endpoint has happy path + auth rejection + primary error path tested
- [ ] No `# pragma: no cover` added to lines an existing test already covers
- [ ] No stacked fix/cleanup commits on top of the feature delivery commit

---

## Coverage Pragma Policy

Use `# pragma: no cover` **only** for code that is structurally impossible to reach in a unit test:

| Allowed | Example |
|---------|---------|
| External I/O adapter function | `async def _send_sms(...):  # pragma: no cover` |
| Background fire-and-forget coroutine | `async def _do_retry() -> None:  # pragma: no cover` |
| Dev-only guard | `if os.getenv("MOCK_X") == "true":  # pragma: no cover` (only if test never sets it) |

**Never** use it to paper over a missing test. Run `make cov` first — if the line is already covered (shows in green), the pragma would hurt your coverage score.

When in doubt: write the test instead.

---

## Commit Style

```
feat(scope): add X because Y
fix(scope): correct Z which caused W
test(scope): cover endpoint A — happy path, 403, 404
```

- No `Co-Authored-By` attribution lines
- Scope examples: `sprint6`, `crm`, `ci`, `predictor`, `sms`

---

## Endpoint Checklist (copy into your test file)

```python
# ── <EndpointName> tests ──────────────────────────────────────────────────────
# 1. Happy path → 200/201
# 2. Auth rejection → 403 (HTTPBearer returns 403, not 401, on missing header)
# 3. Primary error path → 404 / 409 / 422
```

---

## CI Gates (must all pass on every push)

| Gate | Threshold |
|------|-----------|
| Test coverage | ≥ 80% |
| Red-team safety eval | 100% strict pass, 0 infra errors |
| ML model quality (if report exists) | F1 ≥ 0.80, AUC ≥ 0.87 |
| OWASP ZAP scan (weekly) | 0 High-risk alerts |
