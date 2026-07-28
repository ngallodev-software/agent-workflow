# BKL-001 evidence recovery assignment

You are recovering durable evidence for BKL-001 in an existing dedicated worktree.
This is not a new implementation and must not rewrite the historical run
`bkl-001-implementation-luna-20260727`, which remains interrupted because its
completion sidecar was never finalized.

Use the current worktree and the ticket as authority. Do not modify source,
tests, schemas, documentation, the canonical backlog, or pack manifests. Do
not commit. Do not create placeholder evidence. The only permitted writes are
the runner-owned handoff directory and ordinary test/cache output that the
runner scope policy permits.

Before doing anything, inspect the current diff against base revision
`e1141f12df700c1b51878242d83232f96361972a`, confirm the worktree is the
dedicated BKL-001 worktree, and read the BKL-001 ticket plus the completion
template. Validate that the implementation is in scope and that the original
run's missing sidecar is not being silently promoted to success.

Run these exact acceptance commands and record their exit codes and useful
receipt paths:

```text
python3 -m pytest -q tests/invariants/test_consumer_cursors.py tests/acceptance/test_consumer_cursor_journey.py
python3 -m compileall -q src/agent_workflow
```

Inspect the implementation and tests sufficiently to report each BKL-001
acceptance/security criterion as `pass`, `fail`, or `not_verified`. If any
criterion is not evidenced, preserve that uncertainty in `unresolved`; never
turn a missing crash-injection or review artifact into a pass by inference.

Before exiting, write a substantive JSON completion handoff atomically to
`AGENT_WORKFLOW_HANDOFF_DIR/completion.json` using
`agent-workflow/completion/v1`. Include:

- `session_id` from `AGENT_WORKFLOW_SESSION_ID`;
- `ticket_id: BKL-001` and `pack_id: orchestrator-two-way-messaging`;
- base revision and current HEAD revision;
- the exact changed-file list from the worktree diff;
- every acceptance/security criterion with evidence;
- both commands above with exit codes and receipt references;
- every unresolved limitation, especially missing original-run evidence;
- `result: completed` only if all declared acceptance criteria are evidenced,
  otherwise `partial`, `failed`, or `blocked` as appropriate.

Also write a concise `completion.md` in the same handoff directory if useful.
Do not write to the runner-owned state directory. Emit only concise durable
progress updates and exit cleanly so agent-workflow can collect, evaluate, and
seal the run.

This recovery is governed by the communication-reliability remedies: child
handoffs are append-only, silent panes are not health evidence, completion
validation rejects placeholders, and completion, receipt, evaluation, and
ledger artifacts remain distinct.
