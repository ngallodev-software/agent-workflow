# Run retention and rework analysis

## Snapshot

The current `agent-workflow list --json` inventory contains 132 active-state
records:

| Durable state | Count |
| --- | ---: |
| completed | 82 |
| failed | 20 |
| interrupted | 26 |
| killed | 3 |
| running | 1 |

Three records have both `completed` status, an accepted lifecycle disposition,
and a valid collected completion. Only one was eligible for immediate archive
in the dry run because the other accepted records still have tmux sessions that
must be closed explicitly. The remaining records stay visible because their
evidence is incomplete, failed, or not accepted.

The observed failure-category counts were:

| Category | Count |
| --- | ---: |
| unclassified | 10 |
| budget_exhausted | 5 |
| seal_failed | 2 |
| command_not_found | 2 |
| timeout | 1 |
| orphaned | 1 |

The snapshot also contains one orphaned `running` projection for
`tax-p1-sec-001-r5-review`; that is not eligible for archival and should be
recovered or explicitly terminated through the normal lifecycle controls.

## Rework causes

The recurring rework pattern is not simply stale list output:

1. Mutable status was treated as completion authority even when sealed receipt
   or completion collection evidence was missing.
2. Interactive `agent task-complete` was attempted by structured/non-interactive
   agents, where the command is intentionally invalid.
3. Completion handoffs were authored from memory and omitted required schema
   fields, producing invalid collection and repeated review attempts.
4. A completed child process could leave a dead or exited tmux pane/session
   addressable, so closeout was not complete even though the task was finished.
5. There was no recoverable retention operation, so accepted evidence remained
   in the active list and encouraged manual inspection or unsafe cleanup.

The implemented controls address these causes at the boundary:

- launch creates a read-only `completion-template.json` with every required
  completion key and exports `AGENT_WORKFLOW_COMPLETION_TEMPLATE`;
- launch prompts identify the execution mode and explicitly prohibit
  `agent task-complete` for structured runs;
- `archive`/`clear` moves evidence instead of deleting it and requires a valid
  seal, completed/valid handoff collection, accepted lifecycle receipt,
  matching revision, current score digest when applicable, and closed tmux;
- bulk archive is skip-and-report, so one bad run cannot hide other evidence;
- `--dry-run` is the default investigation path and `--verified` is required
  for state-changing moves.

## Operating rule

Use:

```bash
agent-workflow archive --all-verified --dry-run --json
agent-workflow archive SESSION-ID --verified --reason "accepted and retired"
```

Do not delete from the state root directly. A run that fails a gate remains in
`list` and its reported reason is the next recovery action. Archive manifests
are read-only and preserve the source path, archived path, final-receipt digest,
accepted revision, timestamp, and operator reason.
