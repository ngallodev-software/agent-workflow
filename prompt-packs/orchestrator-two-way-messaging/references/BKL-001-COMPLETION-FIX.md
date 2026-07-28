# BKL-001 completion fix

Implement only the missing acceptance evidence for BKL-001 in the existing
dedicated worktree. Do not modify the canonical backlog, prompt-pack manifests,
or unrelated source. Do not commit; the coordinator will inspect and integrate
the branch.

Read the BKL-001 ticket, phase README/master prompt, execution protocol, and
completion template. Inspect the current diff before editing. Preserve the
existing cursor API and source-journal authority.

Add the smallest coherent changes needed to make these acceptance claims
directly observable:

1. The installed-product acceptance journey must use two separate Python
   processes sharing the same durable target and cursor state. The second
   process must demonstrate restart recovery and exactly one semantic target
   effect.
2. Add a focused deletion/reconstruction assertion distinct from the existing
   truncated-cursor case. Reconstruct from source and target evidence without
   losing or duplicating the message.
3. Add an explicit security assertion that source/message content is not
   included in integrity or cursor error text beyond the configured redaction
   policy.
4. Keep the existing crash-window, digest-conflict, independent-consumer, path,
   and trusted-identity coverage.

Use only the ticket writable paths. Do not weaken security checks or change the
authoritative JSONL source journal. Update operations/release documentation
only if public behavior claims need correction. Avoid broad repository
inspection and do not dump large files into the provider stream.

Run and record:

```text
python3 -m pytest -p no:cacheprovider -q tests/invariants/test_consumer_cursors.py tests/acceptance/test_consumer_cursor_journey.py
python3 -m compileall -q src/agent_workflow
```

Write a substantive `agent-workflow/completion/v1` handoff atomically to
`AGENT_WORKFLOW_HANDOFF_DIR/completion.json`, with exact changed files,
criteria, commands/exit codes, and unresolved issues. Report failure rather
than claiming completion if the installed-product journey cannot run.
