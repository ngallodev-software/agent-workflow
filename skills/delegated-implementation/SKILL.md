---
name: delegated-implementation
description: Execute an implementation task as a durable Agent Run with scoped changes, progress, tests, and structured completion evidence.
---

# Delegated Implementation Skill

Use this skill for an implementation task executed as a durable Agent Run.

1. Work only in the assigned source/worktree scope.
2. Read the immutable launch context and task requirements.
3. Emit durable progress at meaningful checkpoints.
4. Apply steering only after recording a correlated acknowledgement.
5. Run the required tests/evaluations.
6. Write the structured completion handoff atomically.
7. Report unresolved items explicitly.
8. Do not self-accept the result; review and acceptance are host/orchestrator responsibilities.
9. Do not create or manipulate an interactive runtime layout as part of task completion.
