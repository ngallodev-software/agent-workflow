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
agent-workflow delegate RUN /path/to/prompt.md --repo REPO --ticket TICKET --base-ref BASE_REF --role implementation --tier medium
```

The positional prompt argument is a path to a regular prompt file, not inline
prompt text. For substantial or reproducible work, keep that file in the
assigned worktree or use `--pack /path/to/pack` for a validated prompt pack.

For an external worker:

```bash
agent-workflow delegate RUN /path/to/prompt.md --workdir WORKTREE --worker-mode external --interactive --role implementation
```

External mode prepares only. Launch the returned worker contract with the external host. Normal agents choose a logical role, never provider/model/runtime routing. Use lower-level `worktree create`, `agent-run prepare`, and `agent-run start` only for recovery, diagnostics, or explicit operator control.

Use the role-scoped launch card/catalog first; retrieve more detail only when needed. Mid-run context and instructions use the single durable steering channel:

```bash
agent-workflow agent-run steer RUN "new instruction or context" --actor parent
agent-workflow agent-run ack RUN MESSAGE_ID "applied" --actor worker
```

The normal worker completion path is one deterministic transaction:

```bash
agent-workflow agent finish RUN --result completed
```

`finish` runs or safely reuses declared acceptance commands, derives explicitly mapped deterministic criteria, and publishes completion only when those gates pass. If it returns a verification failure, repair the reported defect and rerun `finish`. If it requests semantic evidence, record only those listed criteria with `agent criterion`, then rerun `finish`. Use `agent limitation` only for a real controlled-environment limitation.

Do not use routine worker-side status/context/progress/watch polling. Those commands are not part of the worker protocol. Required evaluation, independent review, and authorized acceptance/rejection remain separate host gates. Do not infer success from worker exit or self-accept because implementation/tests finished.

## Launch friction and operator overrides

`--agent-name` is only a logical worker identity. An explicit valid name does not need to appear in `[agents].preferred_names`; that list controls automatic allocation order. A name such as `terra` never selects a model by itself.

Normal orchestration uses `--role`, whose configured private runtime binding owns executor/model/reasoning selection. Do not combine `--role` with explicit runtime overrides. When an operator intentionally needs a specific runtime, omit `--role` and use the matching `--agent-class` together with explicit `--executor`, `--model`, and optional `--reasoning-effort`.

A dirty source tree remains fail-closed. Use `--allow-dirty` only when pre-existing changes are intentionally part of the launch baseline. Agent-Workflow records that drift; workers must preserve unrelated pre-existing changes and must not reinterpret the flag as permission to rewrite them.

Before relying on late steering, inspect the `steering` block returned by `delegate` or the `steering_supported`, `steering_adapter`, and `steering_reason` fields from `agent-run status`. A steering request is persisted even when delivery is `unsupported`; persistence is not application. Treat the request as unapplied until correlated acknowledgement evidence exists.

## Continuous improvement

For every material delegated implementation, prompt-pack execution, recovery, or
review, actively compare the observed outcome with its declared acceptance and
evidence. Record actionable strengths, friction, missing evidence, confusing
contracts, and lifecycle gaps in the durable review/acceptance artifacts or the
Agent-Workflow backlog. Treat a repeated friction point as product-improvement
work without waiting for a separate request. Keep the boundary explicit:
external-host behavior is unverified unless the host supplies evidence, and an
observation must never replace the required evaluation/review/acceptance gates.

## Recovery

Recover from source, the immutable Agent Run contract, append-only journals, sealed evidence, and workflow snapshots. Verify the recorded source/worktree baseline, repair rebuildable projections when needed, then resume scheduling or create lineage with `agent-workflow agent-run restart RUN`. Rerun applicable evaluation before acceptance. Never improvise around or mutate sealed evidence.

## Specialized capabilities

When semantic routing, TypeSafe, comparative decision evidence, decision receipts, or optimization of bounded decisions currently handled by a coding LLM are relevant, read `references/typesafe-semantic-routing.md`. Use TypeSafe/Jev for bounded semantic interpretation and finite choice/ranking/escalation where evidence supports it; keep lifecycle/authorization/verification/review/acceptance authority deterministic. Do not load that reference for ordinary deterministic lifecycle work.


The primary lifecycle remains authoritative. Use specialized skills only for added contracts:
- `delegated-implementation`: worker implementation/completion discipline;
- `phase-gate-review`: independent evidence review;
- `prompt-pack-builder`: reproducible host-independent task/evaluation packs;
- `release-drift-auditor`: release-artifact drift checks.

Prompt packs define reproducible work; ordinary execution still uses `delegate`. Benchmarks are an advanced comparative-evaluation capability, not a normal delegation path.

Escalate to detailed status/context, lower-level commands, recovery docs, or the maintainer CLI only when the scoped runtime contract is incomplete/inconsistent, provenance cannot be reconciled, recovery is required, or an operator/debug capability is intentionally needed.
