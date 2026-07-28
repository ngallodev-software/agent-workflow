# BKL-001 final verification

This is a read-only final verification of the integrated BKL-001 implementation.
Do not edit source, tests, schemas, docs, backlog, or pack files. Do not commit.
Do not inspect broad repository history or dump large files.

Confirm the current repository identity and inspect only the BKL-001 diff and
the focused acceptance/invariant files. Use one targeted codebase-memory query
for the cursor symbols, then stop structural exploration.

Run exactly:

```text
python3 -m pytest -p no:cacheprovider -q tests/invariants/test_consumer_cursors.py tests/acceptance/test_consumer_cursor_journey.py
python3 -m compileall -q src/agent_workflow
```

The focused journey must prove two separate processes share durable cursor and
target state, cursor deletion reconstructs without duplicate effect, crash
windows retry safely, independent consumers remain independent, digest conflicts
fail closed, and error text does not expose source message content.

Write a substantive `agent-workflow/completion/v1` handoff atomically to
`AGENT_WORKFLOW_HANDOFF_DIR/completion.json`, recording exact changed paths,
criteria, commands and exit codes. Mark `completed` only if the commands and
all criteria pass; preserve any environment failure as unresolved. Exit after
the handoff is written.
