# BKL-001 bounded verification

Read-only verification. Do not edit source, tests, schemas, docs, backlog, or
pack files. Do not inspect broad history or dump large files.

First use one narrow codebase-memory-mcp `search_graph` query for `CursorStore`
and do not print a large graph. Then run exactly these commands:

```text
python3 -m pytest -p no:cacheprovider -q tests/invariants/test_consumer_cursors.py tests/acceptance/test_consumer_cursor_journey.py
python3 -m compileall -q src/agent_workflow
```

Write a valid `agent-workflow/completion/v1` JSON handoff atomically to
`AGENT_WORKFLOW_HANDOFF_DIR/completion.json`. Set `base_revision` and
`head_revision` to the exact `git rev-parse HEAD` value. Include the exact
commands, exit codes, seven BKL-001 criteria from the focused tests, changed
paths, and any unresolved environment issue. In every command claim use
`cwd` equal to `.` (the sealed command collector's canonical form). Mark
`result` `completed` only if both commands pass. Exit immediately after
writing the handoff.
