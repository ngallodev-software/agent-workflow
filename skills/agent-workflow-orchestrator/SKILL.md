---
name: agent-workflow-orchestrator
description: Coordinate multiple durable Agent Runs and workflow DAGs with bounded concurrency, durable messaging, recovery, and independently verified receipts.
---

# Agent-Workflow Orchestrator

Use this skill for multi-run coordination or a dependency-ordered workflow. Use
`skills/agent-workflow/SKILL.md` for the lifecycle contract of each run.

## Authority and scheduling

1. Define the parent workflow, immutable source/worktree baseline, task IDs,
   prerequisites, roles, budgets, and the bounded concurrency policy.
2. Validate the workflow snapshot before execution, then start or resume it:

   ```bash
   agent-workflow workflow validate SNAPSHOT
   agent-workflow workflow start RUN_DIR SNAPSHOT
   # after restart:
   agent-workflow workflow resume RUN_DIR SNAPSHOT
   ```

3. Prepare children with the deterministic facade. Use logical roles, never
   provider/model/runtime routing:

   ```bash
   agent-workflow delegate CHILD_ID /path/to/prompt.md --repo REPO --ticket TICKET \
     --base-ref BASE_REF --role implementation --tier medium
   ```

   `delegate` reads its positional prompt argument as a regular file path;
   inline prose is not accepted. Use a durable prompt file or `--pack` for a
   validated prompt pack.

   For a worker owned by another runtime, use `--workdir WORKTREE
   --worker-mode external --interactive`; preparation is not execution. Use
   lower-level `agent-run prepare` or `start` only for recovery or explicit
   operator control. `start` is only for Agent-Workflow-owned headless runs.

4. If a shared orchestrator registry is needed, create it once and register
   only launch-verified children:

   ```bash
   agent-workflow orchestrator registry create ORCHESTRATOR_ID \
     --workflow-id WORKFLOW_ID
   agent-workflow orchestrator registry register ORCHESTRATOR_ID CHILD_ID
   ```

   Keep dependencies explicit in the workflow; do not encode runtime topology
   in hierarchy authority. Run independent children concurrently only within
   the declared bound; schedule dependants after prerequisite evidence exists.

## Persist-first communication

Steering is durable state, not a terminal wake-up. Persist it before delivery,
then require an acknowledgement correlated to the returned message ID:

```bash
agent-workflow agent-run steer CHILD_ID "instruction" --actor PARENT_ID
agent-workflow agent-run message-state CHILD_ID
agent-workflow agent-run ack CHILD_ID MESSAGE_ID "applied" --actor CHILD_ID
```

Use progress for durable checkpoints:

```bash
agent-workflow agent-run progress CHILD_ID "checkpoint" --actor CHILD_ID
```

For shared child journals, import and inspect bounded inbox events. `watch` is
an operational supervisor, not lifecycle authority:

```bash
agent-workflow orchestrator inbox import ORCHESTRATOR_ID
agent-workflow orchestrator inbox read ORCHESTRATOR_ID --include-content
agent-workflow orchestrator watch ORCHESTRATOR_ID --max-cycles 10
```

Transport delivery, worker exit, or an uncorrelated acknowledgement never
proves that a request was applied.

## Gates and receipts

Keep these gates separate and record evidence for each child and the parent:

1. worker execution/exit;
2. structured completion (`agent-workflow agent task-complete`);
3. deterministic evaluation and prerequisite transition;
4. independent review (`agent-run review`);
5. authorized acceptance/rejection (`agent-run accept` or `reject`).

Inspect the durable summary before any disposition:

```bash
agent-workflow agent-run summary CHILD_ID
agent-workflow workflow status RUN_DIR SNAPSHOT
agent-workflow workflow seal RUN_DIR SNAPSHOT
agent-workflow workflow verify RUN_DIR SNAPSHOT
```

Acceptance requires the recorded completion, passing deterministic scores,
prior review, matching revision, and applicable policy evidence. Never infer
acceptance from tests, completion, a green worker process, or a watch cycle.
Unregister children only after their terminal disposition:

```bash
agent-workflow orchestrator registry unregister ORCHESTRATOR_ID CHILD_ID \
  --state completed
```

## Recovery

On interruption, reconcile source/worktree provenance, workflow snapshot,
append-only journals, sealed evidence, and the durable run summary. Repair only
rebuildable projections, then resume. If a completed run must be retried, create
lineage rather than rewriting evidence:

```bash
agent-workflow agent-run repair CHILD_ID
agent-workflow agent-run restart CHILD_ID --new-agent-run-id RETRY_ID
```

For external workers, use the binding and pending-delivery/report commands;
observations and delivery attempts cannot complete, review, or accept a run.

Do not expose host-local paths, select a model/provider, mutate sealed evidence,
or substitute UI/terminal state for Agent-Workflow authority.
