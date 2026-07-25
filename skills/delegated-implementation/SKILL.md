---
name: delegated-implementation
description: Execute bounded implementation tickets already launched through agent-workflow with strict scope, durable evidence, and test controls.
---

# Delegated implementation

Use this skill inside a bounded ticket session that was launched through the `agent-workflow` CLI. For orchestration and lifecycle commands, use [`agent-workflow-orchestrator`](../agent-workflow-orchestrator/SKILL.md).

## Required behavior

1. Read the ticket, phase README, master prompt, execution protocol, and named references.
2. Verify current source before editing.
3. Stay inside writable paths.
4. Implement the smallest coherent change.
5. Add only tests tied to explicit acceptance criteria or a demonstrated regression.
6. Emit durable `progress` records at meaningful checkpoints and `ack` correlated steering messages when the configured executor adapter supports semantic delivery.
7. Preserve failed commands and unresolved contradictions in the completion report.
8. Do not merge, broaden scope, or claim phase acceptance.

## Terminal contract

The operator must launch the ticket with `agent-workflow launch`. Do not create tmux sessions or panes directly. Do not spawn a replacement coding agent from inside the ticket session unless the ticket explicitly assigns coordinator behavior.

A host-native child process or subagent is not an `agent-workflow` run unless an explicit bridge launches it through the CLI and records receipts.

## Stop conditions

Stop rather than guess when current source would make the ticket destructive, a required dependency is absent, a migration cannot be made recoverable, or secrets/real target data would be exposed.

## Structured result and workflow child contract

When the ticket declares a result schema, write only the declared bounded `result.json` contract and ensure it validates before completion. A downstream workflow receives copied values through `workflow-inputs.json`; it must not open predecessor run directories or mutable status projections directly.

For structured executor runs, preserve raw event output. Do not rewrite provider usage, invent cost, or convert missing evidence into zero. Report retries, steering, and errors honestly in the completion handoff.
