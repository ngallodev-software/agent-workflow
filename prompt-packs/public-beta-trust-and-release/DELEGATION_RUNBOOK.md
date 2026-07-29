# Delegation Runbook

## Preflight

```bash
agent-workflow doctor
agent-workflow config show
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
agent-workflow worktree create /path/to/repository TICKET-ID HEAD
```

Confirm the ticket's `backlog_id` is owned by exactly one active prompt pack and that all external prerequisites are complete before launch.

Immediately after worktree creation, follow
[`docs/references/WORKTREE_PREFLIGHT.md`](../../docs/references/WORKTREE_PREFLIGHT.md):
probe the optional service once and, when available, full-index and verify the
exact worktree, record readiness/counts, and refresh before handoff. If it is
unavailable, record the limitation and use bounded RTK discovery without
retrying or blocking the run. This operator check must not become an
application dependency on MCP.

## Parallel launch

Tasks with no dependency edge between them may run concurrently in separate worktrees and sessions. Never place two agents in the same writable worktree.

```bash
agent-workflow launch project-ticket-a /path/to/worktree-a /path/to/pack/phase-0/tickets/TICKET-A.md \
  --ticket TICKET-A --pack /path/to/pack --executor codex
agent-workflow launch project-ticket-b /path/to/worktree-b /path/to/pack/phase-0/tickets/TICKET-B.md \
  --ticket TICKET-B --pack /path/to/pack --executor claude
```

The prompt is passed to the command over standard input. Use the pack's dependency graph as the authority for parallelism; prose ordering does not override manifest dependencies.

## Workflow skills

| Purpose | Codex | Claude |
|---|---|---|
| Build a prompt pack | `$prompt-pack-builder` | `/prompt-pack-builder` |
| Implement one ticket | `$delegated-implementation` | `/delegated-implementation` |
| Review a completed phase | `$phase-gate-review` | `/phase-gate-review` |
| Audit backlog, pack, docs, and release drift | `$release-drift-auditor` | `/release-drift-auditor` |

## Observe and foreground

```bash
agent-workflow list
agent-workflow status SESSION --capture 60
agent-workflow attach SESSION
agent-workflow tail SESSION
```

`possibly_stalled` is advisory. It means tmux is alive while the log has not grown during the configured threshold.

## Stall handling

1. Run `status --capture 100`.
2. Attach to the session.
3. Classify input wait, package/network wait, test deadlock, model loop, or legitimate long operation.
4. Interrupt without deleting evidence.
5. Correct the prompt or environment.
6. Restart into a new retry session so lineage remains explicit.

## Stop controls

```bash
agent-workflow interrupt SESSION
agent-workflow terminate SESSION --grace-seconds 8
agent-workflow kill SESSION
```

Use immediate kill only for an unresponsive process. All controls preserve durable evidence.

## Completion, integration, and review

Require a ticket completion report. Integrate parallel tickets only after inspecting each complete diff and resolving overlap intentionally. Rerun the shared acceptance journeys after integration, not only in each ticket worktree.

Before the phase gate:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
pytest
```

Then apply the `phase-gate-review` and `release-drift-auditor` skills. A high-risk implementer must not be the only reviewer, and actor labels alone do not prove reviewer independence.
