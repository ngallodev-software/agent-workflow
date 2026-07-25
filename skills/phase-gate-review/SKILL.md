---
name: phase-gate-review
description: Independently review completed agent-workflow phases, inspect durable evidence, rerun gates, and issue an accept or reject decision.
---

# Independent phase-gate review

Use this skill after all implementation tickets in a phase have completion reports. Use [`agent-workflow-orchestrator`](../agent-workflow-orchestrator/SKILL.md) for `status`, `review`, `accept`, and recovery commands.

## Review duties

- inspect complete diffs and writable-scope compliance;
- inspect authoritative run artifacts and sealed receipts through the CLI;
- treat terminal capture and tmux output as context, not proof of completion;
- independently rerun the smallest gate commands;
- verify migration/recovery and secret handling manually;
- reject unrelated cleanup and superfluous tests;
- compare documentation claims with implemented behavior;
- confirm ticket dependencies and unresolved issues;
- record `review`, then `accept` or `reject`, only after evidence is checked;
- produce a phase-gate report with an explicit decision.

The gate reviewer must not merely summarize implementer reports or accept an unsealed terminal claim as durable evidence.

## Workflow and provider gates

For workflow phases, verify the stored snapshot, contiguous event journal, exact node set, approval receipt chains, input-binding digests, child final receipts, retry lineage, and aggregate workflow receipt. Mutating `status.json` must not create approval or change sealed evidence.

For benchmark phases, inspect bounded raw events and `provider-evidence.json`; confirm delta/cumulative/terminal semantics, cached/reasoning subset handling, cost/currency/catalog rules, and incomplete-trial rejection. Record unavailable paid/external cohorts rather than simulating them.
