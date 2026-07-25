# Operations

This document consolidates day-to-day delegation lifecycle, agent policy, recovery, and host-routing guidance.

## Execution model

Each delegation has:

- a source repository and pinned baseline revision;
- a dedicated Git worktree;
- a fresh session ID and durable run directory;
- a copied and hashed prompt;
- a configured executor/model/class selection or explicit argv;
- a tmux session or pane used as an observation and process-control surface;
- sealed terminal evidence and later immutable lifecycle receipts.

The CLI and MCP adapter call shared services. Shell scripts are compatibility wrappers only.

## Launch policy

Agent classes constrain interactivity, executor, and model combinations. Named profiles may narrow those choices but cannot escape class policy. Explicit no-go authorization is recorded in provenance.

Routing advice is deterministic and explainable, but advisory. The launch plan produced by configured policy is authoritative. Never allow a recommendation, prior trial, or agent-selected value to bypass class, executor, model, or permission restrictions.

The default classes are:

| Class | Intended use | Default behavior |
|---|---|---|
| `exploratory` | bounded research and reconnaissance | non-interactive, low-cost models |
| `review` | independent inspection and evidence review | non-interactive |
| `implementation` | code-changing work | interactive by default |

The concrete allowlists live in configuration, not documentation. Use `agent-workflow config show` to inspect effective policy.

## Observe and control

```bash
agent-workflow list
agent-workflow status SESSION --capture 50
agent-workflow attach SESSION
agent-workflow tail SESSION
```

Controls preserve prior evidence:

```bash
agent-workflow interrupt SESSION
agent-workflow terminate SESSION
agent-workflow kill SESSION
agent-workflow restart SESSION --new-session RETRY_SESSION
```

A potential stall is a diagnostic state, not authorization to terminate. Inspect terminal liveness, heartbeat, lifecycle events, log movement, and durable messages before acting.

## Durable messages

The fsynced message journal is the authority. tmux `wait-for` is a local wakeup accelerator only. Producers append immutable records; consumers replay by sequence and acknowledge work explicitly.

```bash
agent-workflow steer SESSION "Run the focused tests." --actor orchestrator
agent-workflow watch SESSION --after 0 --timeout 300
agent-workflow progress SESSION "Focused tests passed." --actor child
agent-workflow ack SESSION MESSAGE_ID "Applied." --actor child
```

A steer is pending until correlated acknowledgement exists. Logs, terminal text, or a live tmux process do not prove delivery or application.

## Interactive agent reuse

Interactive agents can retain bounded assignment context. Reuse requires:

- explicit prior task completion;
- an idle, live, unexpired session;
- the exact same worktree;
- a compatible agent policy;
- exact ticket/retry lineage for automatic reuse;
- correlated acknowledgement of the reassignment.

```bash
agent-workflow agent task-complete SESSION --actor AGENT --summary "Implemented parser"
agent-workflow agent candidates /path/to/worktree --ticket TICKET --pack PACK
agent-workflow agent reuse SESSION ./next-task.md --actor orchestrator --ticket TICKET --pack PACK
```

Similarity ranking helps an operator choose; it is not autonomous memory or routing authority.

## Workflow recovery

Workflow snapshots are immutable and event journals append-only. To recover after interruption:

1. verify the supplied snapshot is identical to the started snapshot;
2. run `workflow status` to refresh projections from the journal;
3. inspect child run evidence for running or terminal nodes;
4. run `workflow resume` to reconcile and schedule eligible work;
5. seal only after every node is terminal.

Never edit `workflow-status.json` to repair state. It is a projection.

## Worktree and evidence cleanup

Do not delete a failed worktree or run directory automatically. Review the patch and receipts first. Removing a worktree does not remove the authoritative XDG run evidence.

Use `worktree remove` only after deciding whether the branch should be retained. Use uninstall only for installer-owned links and launchers; unrelated paths are left untouched.

## Host routing

Global instructions may recommend `agent-workflow` for bounded delegation. They are guidance, not a security boundary. Future installer-owned hooks may block a narrowly defined set of direct delegation commands, but only after explicit maintainer authorization and an audited break-glass path. See `BKL-007` in [BACKLOG.md](../BACKLOG.md).
