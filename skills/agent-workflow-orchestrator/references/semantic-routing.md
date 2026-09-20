# Semantic routing in orchestration

Read this only when an orchestrated workflow enables a non-deterministic Agent-Workflow decision mode.

Semantic routing is owned by each Agent-Workflow routing boundary; the orchestrator does not call TypeSafe directly and does not reinterpret provider probabilities. Prepare/delegate children using logical roles and the normal routing API. When comparative or TypeSafe mode is configured, Agent-Workflow obtains semantic evidence inside that boundary and records decision receipts.

For detailed TypeSafe input/result semantics, load `references/typesafe-semantic-routing.md` from the primary `agent-workflow` skill.

Orchestration invariants remain deterministic: workflow dependencies, concurrency bounds, run identity, ownership, restart lineage, evidence gates, review, and acceptance cannot be overridden by semantic-provider output. Comparative evidence may inform later calibration or review, but it is not a scheduling/lifecycle authority.
