---
name: agent-workflow-orchestrator
description: Coordinate multiple durable Agent Runs and workflow DAGs with bounded concurrency, delegation authority, messaging, and receipts.
---

# Agent-Workflow Orchestrator Skill

Use this specialization when coordinating multiple durable Agent Runs or a workflow DAG.

- Create/validate workflow authority before launching workers.
- Delegate through Agent Runs, not UI objects.
- Prefer bounded parallelism and explicit dependencies.
- Persist parent-to-child steering before delivery.
- Require correlated acknowledgements.
- Treat child completion evidence as an input to workflow transition, not as acceptance by itself.
- Use hierarchy contracts only for durable authority, capability narrowing, budget narrowing, journals, and receipts.
- Keep any future runtime topology outside hierarchy authority.

For individual Agent Run semantics, follow `skills/agent-workflow/SKILL.md`.
