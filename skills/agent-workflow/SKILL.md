---
name: agent-workflow
description: Use Agent-Workflow for durable Agent Runs, evidence, evaluation, review, and host-independent workflow authority.
---

# Agent-Workflow Skill

Use Agent-Workflow when delegated engineering work needs durable identity, restartability, provenance, steering, evaluation, review, or auditable completion. Do not invoke it merely because it is available.

## Use / do not use

Use it for delegated coding, long-running or restart-sensitive work, multi-agent/dependency-ordered work, isolated worktrees, durable coordination, structured completion/evaluation/review, prompt-pack execution, or benchmarked/audited work.

Normally skip it for read-only explanation/review with no delegated execution, one deterministic local command, a trivial caller-owned edit with no evidence/review contract, or brainstorming that has not become an implementation task.

## Durable model

```text
Workflow -> Task -> Agent Run -> Worker
```

`agent_run_id` is the durable execution identity. A Worker is only the actor attached to that run; process/UI/host identity never replaces the Agent Run.

Worker modes:
- `headless`: Agent-Workflow launches and owns the local worker process group.
- `external`: Agent-Workflow prepares the durable run/launch contract; another runtime launches the worker.

External hosts are execution/presentation adapters only. They do not replace Agent-Workflow identity, messaging, source/worktree provenance, evidence, review, or acceptance authority. Never make terminal-manager behavior part of the lifecycle.

## Invariants

1. Preserve the Agent-Workflow-recorded source/worktree provenance.
2. Persist steering before live delivery; delivery is not acknowledgement.
3. Acknowledge against the durable message/correlation ID.
4. Worker exit != completion != evaluation != review != acceptance.
5. Restart/retry creates lineage; never rewrite prior sealed evidence.
6. Mutable status, indexes, and host bindings are projections, not lifecycle authority.

## Default flow

Prefer the deterministic facade; it composes existing worktree/Agent Run authorities rather than creating another lifecycle.

```bash
agent-workflow delegate RUN PROMPT --repo REPO --ticket TICKET --base-ref BASE_REF --role implementation --tier medium
```

For an external worker:

```bash
agent-workflow delegate RUN PROMPT --workdir WORKTREE --worker-mode external --interactive --role implementation
```

External mode prepares only. Launch the returned worker contract with the external host. Normal agents choose a logical role, never provider/model/runtime routing. Use lower-level `worktree create`, `agent-run prepare`, and `agent-run start` only for recovery, diagnostics, or explicit operator control.

Use the role-scoped launch card/catalog first; retrieve more detail only when needed:

```bash
agent-workflow agent-run status RUN
agent-workflow agent context RUN
agent-workflow agent-run progress RUN "checkpoint" --actor worker
agent-workflow agent-run steer RUN "new instruction" --actor parent
agent-workflow agent-run ack RUN MESSAGE_ID "applied" --actor worker
```

Workers publish structured completion with `agent task-complete`. Required evaluation, independent review, and authorized acceptance/rejection remain separate gates. Do not infer success from worker exit or self-accept because implementation/tests finished.

## Recovery

Recover from source, the immutable Agent Run contract, append-only journals, sealed evidence, and workflow snapshots. Verify the recorded source/worktree baseline, repair rebuildable projections when needed, then resume scheduling or create lineage with `agent-workflow agent-run restart RUN`. Rerun applicable evaluation before acceptance. Never improvise around or mutate sealed evidence.

## Specialized capabilities

The primary lifecycle remains authoritative. Use specialized skills only for added contracts:
- `delegated-implementation`: worker implementation/completion discipline;
- `phase-gate-review`: independent evidence review;
- `prompt-pack-builder`: reproducible host-independent task/evaluation packs;
- `release-drift-auditor`: release-artifact drift checks.

Prompt packs define reproducible work; ordinary execution still uses `delegate`. Benchmarks are an advanced comparative-evaluation capability, not a normal delegation path.

Escalate to detailed status/context, lower-level commands, recovery docs, or the maintainer CLI only when the scoped runtime contract is incomplete/inconsistent, provenance cannot be reconciled, recovery is required, or an operator/debug capability is intentionally needed.
