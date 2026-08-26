---
name: delegated-implementation
description: Execute an implementation task as a durable Agent Run with scoped changes, progress, tests, and structured completion evidence.
---

# Delegated Implementation Skill

Use this specialization for worker-side implementation inside an Agent Run. Follow `skills/agent-workflow/SKILL.md` for lifecycle identity, provenance, messaging, recovery, and completion/review/acceptance boundaries.

Implementation-specific responsibilities:

1. Work only in the assigned source/worktree scope and immutable launch contract.
2. Implement the requested change without replacing durable Agent-Workflow authority with host/UI state.
3. Emit durable progress at meaningful checkpoints and acknowledge applied steering by correlation ID.
4. Run the required tests/evaluations for the assignment.
5. Publish the structured completion handoff atomically, including changed files and unresolved items.
6. Do not self-review or self-accept unless the governing contract explicitly assigns an independent role that permits it.
