# delegation-communication-reliability

This pack hardens the delegation control plane exposed by the recent HARD-004
run failures. It makes prerequisite checks use immutable lifecycle evidence,
makes child-to-parent communication observable and correlated, detects silent
or stale runs, and rejects empty completion handoffs.

The pack owns `PROC-001` through `PROC-005`. The canonical unfinished-work
register remains [`docs/BACKLOG.md`](../../docs/BACKLOG.md).

## Execution

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/delegation-communication-reliability
agent-workflow worktree create /path/to/repository PROC-001 HEAD
agent-workflow launch proc-001 /path/to/worktree \
  prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-001-authoritative-preflight.md \
  --ticket PROC-001 --pack delegation-communication-reliability --executor codex --interactive
```

Use a separate worktree and session per ticket. A valid current tmux context
creates a visible pane through `agent-workflow launch`; an unusable context
falls back to a detached named session. Native host subagents are not durable
workflow runs unless explicitly bridged through the CLI.

Implementation tickets start interactive. Only exploration, research, or an
explicit structured-evidence fallback may be non-interactive. Never silently
downgrade because the pane cap is full.

Use codebase-memory for structural discovery first and RTK-wrapped commands for
shell inspection. Run the release-drift audit before the phase gate and before
archiving. A structured provider stream is required for post-run evaluation;
terminal/TUI text is operational context only.

## Phases

1. **Phase 0 — control-plane foundations:** run `PROC-001` through `PROC-004`
   concurrently in isolated worktrees.
2. **Phase 1 — operator enforcement:** run `PROC-005` after the runtime diffs
   are integrated; it updates steering references, hooks/reminders, and
   recovery documentation only where behavior is real.
3. **Phase 2 — independent gate:** run `PROC-GATE-001` after integration,
   shared acceptance journeys, release audit, and pack validation.

The gate may accept only evidence with valid completion collections, sealed
receipts, correlated control events, substantive completion reports, and a
verified ledger row. Do not change backlog status from an external archive.

## Checksums and archive transfer

The archive helper creates a transfer-only `MANIFEST.sha256` and external
archive checksum. They are generated artifacts, not tracked implementation
inputs; repository-wide `*.sha256` files are ignored.
