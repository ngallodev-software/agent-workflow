# Benchmark Enhancements Checkpoint 05 Validation

## Scope

Checkpoint 05 extends the benchmark implementation validation into the shared interactive runner and corrects a control-bridge race discovered by partitioned acceptance testing.

## Defect corrected

A short-lived interactive child could perform all of the following in one polling interval:

1. write a valid `task_complete` control intent;
2. exit successfully;
3. cause the runner to observe process exit before draining the bridge.

The run could then seal as `completed` while `agent-context.json` incorrectly remained in the `busy` state. This produced contradictory durable authority: terminal run status but an unclosed assignment.

## Implementation

`src/agent_workflow/runner.py` now drains control intents at the observed process-exit boundary before finalizing the process return code.

The exception is deliberately narrow:

- a valid `task_complete` intent already present at the exit boundary may be applied;
- non-terminal progress, acknowledgement, steering, malformed, stale, and other post-exit intents remain rejected;
- the normal later `active=False` drain continues to reject arrivals after the boundary.

This preserves the existing post-exit security policy while removing the completion-state race.

## Validation

### Complete invariant suite

```text
283 passed in 18.84s
```

Command:

```bash
python -m pytest -q tests/invariants --disable-warnings --maxfail=1
```

### Focused acceptance regression

```text
2 passed in 19.41s
```

Covered journeys:

- `test_interactive_child_task_complete_uses_bound_cli_and_bridge`
- `test_installed_control_intent_matrix_is_durable_correlated_and_append_only`

The first proves terminal completion closes durable assignment state. The second proves ordinary post-exit intents remain rejected.

## Environment limitation

The complete delegation acceptance file exceeds the bounded command window in this execution environment. No assertion failure was observed after the focused correction; the authoritative focused cases and complete invariant suite are recorded above.
