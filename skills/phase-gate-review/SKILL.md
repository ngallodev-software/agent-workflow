---
name: phase-gate-review
description: Independently review Agent Run or workflow-phase evidence and produce an approval, changes-requested, or blocked gate disposition.
---

# Phase-Gate Review Skill

Use this specialization to independently review completed Agent Runs, workflow phases, or release gates. Follow `skills/agent-workflow/SKILL.md` for the authoritative lifecycle, provenance, and acceptance boundaries.

Review the durable evidence required by the governing contract, including the immutable Agent Run/source identity, expected outputs and changed files, completion/unresolved items, required tests/evaluations, worktree/source provenance, relevant message/incident evidence, and any applicable hierarchy receipts or independence requirements.

Record `approved`, `changes_requested`, or `blocked` according to the applicable review contract. Review is evidence for a later authorized acceptance/rejection decision; presentation state, worker exit, or an idle external host is never acceptance evidence.

Before a release gate, invoke `release-drift-auditor` and treat unresolved release drift as blocking evidence.
