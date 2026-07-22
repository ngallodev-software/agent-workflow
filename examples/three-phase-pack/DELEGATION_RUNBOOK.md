# Delegation Runbook

## Preflight

```bash
agent-workflow doctor
agent-workflow config show
agent-workflow pack validate /path/to/prompt-pack
agent-workflow worktree create /path/to/repository P0-01 HEAD
```

## Launch in a fresh terminal

```bash
agent-workflow launch   project-p0-01-components   /path/to/worktree   /path/to/pack/phase-0/tickets/P0-01.md   --ticket P0-01   --pack project-phases-0-2   --executor codex
agent-workflow launch   project-p0-02-components   /path/to/worktree   /path/to/pack/phase-0/tickets/P0-02.md   --ticket P0-02   --pack project-phases-0-2   --executor claude
```

The prompt is passed to the command over standard input.

## Workflow skills

| Purpose | Codex | Claude |
|---|---|---|
| Build a prompt pack | `$prompt-pack-builder` | `/prompt-pack-builder` |
| Implement one ticket | `$delegated-implementation` | `/delegated-implementation` |
| Review a completed phase | `$phase-gate-review` | `/phase-gate-review` |

## Observe and foreground

```bash
agent-workflow list
agent-workflow status project-p0-01 --capture 60
agent-workflow attach project-p0-01
agent-workflow tail project-p0-01
```

`possibly_stalled` is advisory. It means tmux is alive while the log has not grown during the configured threshold.

## Stall handling

1. Run `status --capture 100`.
2. Attach to the session.
3. Classify input wait, package/network wait, test deadlock, model loop, or legitimate long operation.
4. Interrupt without deleting evidence.
5. Correct the prompt or environment.
6. Restart into a new `-retryN` session.

## Stop controls

```bash
agent-workflow interrupt SESSION
agent-workflow terminate SESSION --grace-seconds 8
agent-workflow kill SESSION
```

Use immediate kill only for an unresponsive process. All controls preserve durable evidence.

## Completion and review

Require a ticket completion report, inspect the diff before running tests, independently rerun narrow acceptance commands, and create a phase-gate report. A high-risk implementer should not be the only reviewer.
