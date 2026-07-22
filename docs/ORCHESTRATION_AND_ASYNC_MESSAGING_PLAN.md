# Orchestration, tmux panes, and asynchronous updates

## Current behavior

`agent-workflow` uses a durable-polling design. Each launch owns a unique
logical session ID, a detached tmux session of the same name, and a durable
XDG run directory. The runner records status, normalized output, optional raw
executor events, heartbeat, completion sidecars, lifecycle events, and a final
receipt. An orchestrator uses `list` and `status` to observe these artifacts;
there is no automatic callback or agent-to-agent mailbox.

This is intentional: launched agents remain isolated and an interrupt or kill
can target one workflow run without affecting an orchestrator or another agent.
The durable completion JSON and final receipt are the authoritative completion
handoff, not terminal text.

## Recommendation: retain polling as the baseline

Do not introduce Redis, NATS, or another external broker for the current local,
single-host workflow. The existing run directory is durable, inspectable,
replayable, and already survives a tmux or client failure. Polling is sufficient
for launch, observe, review, and retry.

The orchestrator should:

1. launch each bounded ticket with a unique workflow session ID;
2. poll `status --json` at a bounded interval, using heartbeat/log freshness as
   progress signals;
3. treat a terminal status plus verified `final-receipt.json` as completion;
4. read `completion.json`, review receipts, and sealed evaluation reports before
   scheduling dependent work;
5. keep interruption, retry, review, and acceptance under operator control.

## Optional pane mode

The current tmux backend creates a new detached tmux **session** for every
workflow session. It cannot safely launch into a pane in an existing session:
its operations currently address the whole tmux session, so a kill would risk
killing the orchestrator as well.

If a supervised control-room layout becomes a real requirement, add an opt-in
pane backend without changing the default isolation model.

| Requirement | Pane-backend design |
|---|---|
| Create | `tmux split-window -d` against an explicit parent target. |
| Identity | Persist a unique pane target (`session:window.pane`) separately from the logical workflow session ID. |
| Observe | Capture pane, PID, and death state by pane target. |
| Lifecycle | Send interrupts and kill only the pane; never call `kill-session` for pane-mode runs. |
| Attach | Select/switch to the pane instead of attaching by workflow session ID. |
| Failure | If the parent session disappears, report `terminal_unavailable` or `orphaned` without changing durable evidence. |
| Safety | Require `--tmux-parent` or an explicit configuration value; preserve isolated sessions as the default. |

Do not overload a session ID as a tmux target. A `TerminalTarget` abstraction
should own session-mode versus pane-mode addressing before the backend changes.

## When asynchronous messaging is justified

Add messaging only if polling demonstrably blocks useful work—for example,
automatic release of dependency-ready tickets, a human needing a structured
progress update before completion, or a multi-process orchestrator that must
resume after restart without scanning all runs.

Start with a durable, local append-only mailbox instead of an external broker:

```text
<pack-run-root>/messages.jsonl
  sequence, timestamp, sender, recipient, kind, run_id, artifact_refs, payload
```

Rules:

- serialize appends with the same file-locking and fsync discipline used for
  lifecycle events;
- use messages as notifications and references, never as authority over run
  state or receipts;
- keep payloads bounded and store large/log-sensitive content in sealed
  artifacts referenced by hash/path;
- allow the orchestrator to reconstruct state by replaying the log after a
  restart;
- keep agent writes constrained to predefined message kinds such as `progress`,
  `blocked`, `completion_ready`, and `review_requested`.

Only consider a broker after there is a proven cross-host, fan-out, or
low-latency requirement that the durable mailbox cannot satisfy.

## Implementation order

1. Fix sealing and explicit-command metadata regressions first; reliable final
   receipts are prerequisite to orchestration.
2. Add a polling-oriented orchestration API/MCP read surface if clients need
   structured access.
3. Add a pane backend only with explicit operator demand and pane-scoped
   lifecycle tests.
4. Add a local durable mailbox only after observed scheduling friction.
5. Keep remote transport, daemonization, autonomous merge/kill, and external
   message infrastructure out of scope until separately justified.
