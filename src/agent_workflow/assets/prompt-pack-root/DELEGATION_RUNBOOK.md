# Delegation Runbook

## Preflight

```bash
agent-workflow doctor
agent-workflow config show
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
agent-workflow worktree create /path/to/repository TICKET-ID HEAD
```

Confirm the ticket's `backlog_id` is owned by exactly one active prompt pack and that all external prerequisites are complete before preparing an Agent Run.

Apply `docs/references/WORKTREE_PREFLIGHT.md` to the exact worktree. Optional discovery/indexing services remain operator conveniences and must not become runtime dependencies.

## Prepare and start Agent Runs

Tasks with no dependency edge may run concurrently in separate worktrees. Never place two workers in the same writable worktree.

For an Agent-Workflow-owned headless worker:

```bash
agent-workflow agent-run prepare project-ticket-a /path/to/worktree-a /path/to/pack/phase-0/tickets/TICKET-A.md \
  --ticket TICKET-A --pack /path/to/pack --role implementation --worker-mode headless
agent-workflow agent-run start project-ticket-a
```

For a future external interactive host, prepare only:

```bash
agent-workflow agent-run prepare project-ticket-b /path/to/worktree-b /path/to/pack/phase-0/tickets/TICKET-B.md \
  --ticket TICKET-B --pack /path/to/pack --role implementation --worker-mode external
```

The external host owns presentation and live interaction. Agent-Workflow remains authoritative for the Agent Run, durable messages, evidence, completion, evaluation, and review.

## Observe

```bash
agent-workflow agent-run list
agent-workflow agent-run status AGENT-RUN-ID
agent-workflow agent-run tail AGENT-RUN-ID
```

`possibly_stalled` is advisory. It means the worker is still observed as running while durable/log progress has not advanced during the configured threshold. Inspect evidence before interrupting it.

## Durable communication

Persist workflow instructions before attempting any live delivery:

```bash
agent-workflow agent-run steer AGENT-RUN-ID "Re-run the integration suite"
agent-workflow agent-run progress AGENT-RUN-ID --message "Integration suite running"
agent-workflow agent-run ack AGENT-RUN-ID MESSAGE-ID
```

Delivery by an external host is not an acknowledgement. The worker records the acknowledgement through Agent-Workflow.

## Retire verified runs

`agent-workflow agent-run list` is the active Agent Run view. Retire completed work only through the recoverable archive command; never delete a run directory by hand:

```bash
agent-workflow archive --all-verified --dry-run --json
agent-workflow archive AGENT-RUN-ID --verified --reason "accepted and no longer active"
```

The command rechecks durable evidence and accepted lifecycle state before moving the Agent Run from the active root to archive storage.

## Stall handling

1. Inspect `status` and `tail`.
2. Classify input wait, package/network wait, test deadlock, model loop, or legitimate long operation.
3. Interrupt without deleting evidence.
4. Correct the prompt or environment.
5. Restart into a new Agent Run so lineage remains explicit.

## Lifecycle controls

Only the workflow authority should issue semantic lifecycle controls:

```bash
agent-workflow agent-run interrupt AGENT-RUN-ID
agent-workflow agent-run terminate AGENT-RUN-ID --grace-seconds 8
agent-workflow agent-run restart AGENT-RUN-ID
```

For headless workers, Agent-Workflow signals its owned process group. For externally hosted workers, Agent-Workflow records the requested semantic action for the host to reconcile. Controls preserve durable evidence.

## Completion, integration, and review

Require a structured completion report. Integrate parallel tickets only after inspecting each complete diff and resolving overlap intentionally. Rerun shared acceptance journeys after integration.

Before the phase gate:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate /path/to/prompt-pack
pytest
```

A high-risk implementer must not be the only reviewer. Actor labels alone do not prove reviewer independence.
