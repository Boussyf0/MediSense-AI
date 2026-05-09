## What & Why
<!-- One paragraph: what this PR does and why it is needed -->

## Test evidence
- [ ] `make test` passes locally — all tests green, coverage ≥ 80%
- [ ] `make cov` shows no uncovered lines in new or changed files
- [ ] New endpoints: happy path (200/201) + auth rejection (403) + error path (404/409/422) all tested
- [ ] No `# pragma: no cover` added to lines an existing test already covers

## Checklist
- [ ] No stacked fix/cleanup commits — feature is done in one shot
- [ ] GHCR image name uses `github.repository_owner`, not `github.repository`
- [ ] Any `# pragma: no cover` usage has a comment explaining why it cannot be tested
- [ ] `await db.flush()` used inside endpoints, never `db.commit()`
