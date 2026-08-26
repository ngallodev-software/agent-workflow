---
name: phase-gate-review
description: Independently review Agent Run or workflow-phase evidence and produce an approval, changes-requested, or blocked gate disposition.
---

# Phase-Gate Review Skill

Use this skill to independently review completed Agent Runs, workflow phases, or release gates.

Review durable evidence rather than presentation state. Verify:

- immutable Agent Run/source identity;
- required outputs and changed files;
- completion schema and unresolved items;
- required commands/tests and evaluator results;
- source revision and worktree provenance;
- message/incident evidence relevant to the gate;
- hierarchy narrowing/receipts where applicable;
- review independence requirements.

A worker's exit or idle state is never proof of acceptance. Record `approved`, `changes_requested`, or `blocked` review disposition according to the applicable contract, then leave final acceptance to the authorized lifecycle command.

Before a release gate, invoke the `release-drift-auditor` skill and treat unresolved release drift as blocking evidence.
