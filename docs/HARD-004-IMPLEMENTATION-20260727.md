# HARD-004 implementation evidence

Captured 2026-07-27 after the delegated HARD-004 candidates stalled without
valid completion contracts. The coordinator completed the bounded implementation
on top of `dfb0db1`.

## Implemented authority

- `launch-contract.json` is immutable launch authority for runner, collectors,
  evaluation, status projection repair, and receipt verification.
- Mutable `status.json` fields are projected from the launch contract rather than
  selecting the executor, worktree, prompt, result schema, or evaluation policy.
- Runtime executor argv is carried to the generated runner as encoded data and
  bound to the contract with a SHA-256 digest; redacted argv remains in persisted
  JSON artifacts.
- Anonymous task-result schemas bind to their pack-relative schema path and
  content digest instead of requiring a caller-supplied `$id`.
- Disposable handoff/delegation trees are excluded from writable-scope
  violations while repository changes remain enforced.

## Verification

Using the repository `.venv`, with ambient tmux variables removed:

```text
tests/acceptance/test_delegation_journeys.py: 5 passed
focused HARD-004 regression slice: 8 passed
scripts/release-check.sh: 62 passed, 2 skipped, 5 strict xfailed
scripts/audit-release-assets.py: valid
prompt-pack validation: deterministic foundations valid; messaging pack valid
```

The strict future authority journey remains an expected failure until the
shared foundation phase gate records an independent sealed disposition. This
document records implementation and installed-product evidence; it does not
claim that phase-gate acceptance already exists.
