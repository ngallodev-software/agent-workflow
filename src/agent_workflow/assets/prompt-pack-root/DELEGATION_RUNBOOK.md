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

Immediately after worktree creation, apply the repository procedure in
`docs/references/WORKTREE_PREFLIGHT.md`: probe the optional codebase-memory
service once and, when available, index the exact worktree, verify readiness,
and record identity/counts. Do not substitute an index from the main checkout.
When unavailable, record the limitation and use bounded RTK shell discovery;
do not retry or block the run. This operator check must not become an
`agent-workflow` package or runtime dependency.

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

## Retire verified runs

`agent-workflow list` is the active-run view. Retire completed work only through
the recoverable archive command; never delete a run directory by hand:

```bash
agent-workflow archive --all-verified --dry-run --json
agent-workflow archive SESSION-ID --verified --reason "accepted and no longer active"
```

The command rechecks the sealed receipt, completion collection, accepted
lifecycle chain, revision, evaluation score digest when present, and tmux
closure before moving the directory from the active `runs/` root to the state
`archive/` root. Failed candidates remain in `list` with their evidence and
are reported by the bulk dry run.

## Stall handling

1. Run `status --capture 100`.
2. Attach to the session.
3. Classify input wait, package/network wait, test deadlock, model loop, or legitimate long operation.
4. Interrupt without deleting evidence.
5. Correct the prompt or environment.
6. Restart into a new retry session so lineage remains explicit.

## Stop controls

Only the host orchestrator may use lifecycle controls. A sandboxed child must
write its completion handoff, invoke `agent task-complete` once, and exit
normally; the host runner owns tmux, canonical state, and final sealing.

Before writing a completed handoff, an implementation agent commits all source,
test, and documentation changes. Its sidecar records the launch baseline and
the exact post-commit `git rev-parse HEAD`; every command has an absolute `cwd`
and an exit code. Structured non-interactive runs do not invoke
`agent task-complete`; they write the sidecar and exit for collection. Review
runs follow the same schema-valid sidecar contract and report independently
collected commands and evidence.

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
