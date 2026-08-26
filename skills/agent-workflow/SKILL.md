---
name: agent-workflow
description: Use Agent-Workflow for durable Agent Runs, evidence, evaluation, review, and host-independent workflow authority.
---

# Agent-Workflow Skill

Use agent-workflow when engineering work benefits from durable delegation, restartability, explicit evidence, evaluation, review, or auditable completion.

## Core model

```text
Workflow -> Task -> Agent Run -> Worker
```

An **Agent Run** is one durable execution of a task. A **Worker** is the execution actor attached to that run.

Worker modes:

- `headless`: agent-workflow launches and owns the local process group;
- `external`: agent-workflow prepares the durable run and another runtime launches the worker.

## Mandatory rules

1. Use `agent_run_id` as durable execution identity.
2. Do not identify work by a UI/window/pane/process identifier.
3. Agent-workflow owns worktree/source provenance for the current architecture.
4. Persist steering before any live delivery attempt.
5. Delivery is not acknowledgement; acknowledge with the durable message ID.
6. Worker exit is not completion.
7. Completion is not evaluation.
8. Evaluation is not review.
9. Review is not acceptance.
10. Never make a host-specific runtime a dependency of the core workflow.

## Standard headless flow

```bash
agent-workflow worktree create REPO TICKET BASE_REF
agent-workflow agent-run prepare RUN WORKTREE PROMPT --role implementation --tier medium
agent-workflow agent-run start RUN
agent-workflow agent-run status RUN
```

Use durable progress and steering:

```bash
agent-workflow agent-run progress RUN "checkpoint" --actor worker
agent-workflow agent-run steer RUN "new instruction" --actor parent
agent-workflow agent-run ack RUN MESSAGE_ID "applied" --actor worker
```

After completion, inspect evaluation/evidence and use explicit review/accept/reject lifecycle commands.

## External runtime composition

When an interactive host is available, use its native mechanisms only for presentation/live execution. Prepare the Agent Run with `--worker-mode external`. Do not let the host replace durable AW identity, messaging, evidence, or acceptance authority.
