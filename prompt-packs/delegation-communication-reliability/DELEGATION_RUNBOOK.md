# Delegation runbook

```bash
agent-workflow doctor
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/delegation-communication-reliability
agent-workflow worktree create /path/to/repository PROC-001 HEAD --dest /path/to/worktree
agent-workflow launch proc-001 /path/to/worktree \
  prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-001-authoritative-preflight.md \
  --ticket PROC-001 --pack delegation-communication-reliability \
  --agent-class implementation --executor codex --interactive \
  --pane-limit-action cancel
agent-workflow status proc-001 --capture 60
```

## Launch preflight

Before each implementation launch, record the current revision, branch, clean
state, Python version, pane capacity, ticket ownership, and live prerequisite
dispositions. Prerequisite acceptance comes from lifecycle receipts and
`agent-workflow status --json`, never from a stale `status.json`, terminal text,
or an exported archive.

The launcher must perform a control-plane handshake before work is considered
started: append a child progress event, verify its durable record, and require
a correlated acknowledgement where the executor adapter supports it. A
read-only parent projection is not a writable communication channel.

## Observation and closeout

Treat an alive pane with no heartbeat, output, or executor event as a
communication fault, not as healthy progress. Inspect once, then interrupt or
terminate through the CLI and retry in a new named session/worktree. Preserve
the failed evidence.

At completion, require a non-default schema-valid completion report, a valid
completion collection, final receipt, evaluation collection/report when
required, and ledger row. Close sessions only with `agent-workflow terminate`
and verify `tmux_alive=false` and `pane_dead=true` or an absent pane.

Implementation changes must be committed before the completed handoff is
written. Bind `base_revision` to the launch revision and `head_revision` to the
exact post-commit Git HEAD; use absolute command working directories and exact
exit codes. Structured non-interactive runs write the sidecar and exit without
`agent task-complete`. Independent reviewers provide their own schema-valid
sidecar with independently collected command receipts and criterion evidence.
In `completion.json`, each command object must use `argv`, absolute `cwd`,
integer `exit_code`, and string `receipt`; `commands[].evidence` is invalid.
