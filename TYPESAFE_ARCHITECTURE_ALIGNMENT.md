# TypeSafe architecture alignment

Agent-Workflow owns its bounded semantic decision seams directly. TypeSafe is an optional built-in provider, not an Agent-Workflow plugin and not a lifecycle authority.

```text
projected application state
        -> built-in optional TypeSafe provider
        -> raw Choice / Noul / Score evidence
        -> Agent-Workflow DecisionPolicy
        -> existing deterministic application behavior
```

## Authority

Agent-Workflow owns stable decision IDs, deterministic control values, thresholds, fallback, policy composition, lifecycle/review/acceptance authority, and `agent-workflow/decision-execution-receipt/v1`. TypeSafe cannot bypass executor/model allowlists, lifecycle state, evidence checks, review, or acceptance.

## Provider

The provider lives under `agent_workflow.semantic` and lazy-imports `typesafe-sdk`. It lowers versioned application question specifications to the official SDK `Choice`, `Noul`, and `Score` primitives. Missing SDK/credentials, transport failure, no-match, uncertainty, and policy rejection remain explicit fallback evidence.

The SDK is optional (`agent-workflow[typesafe]`). `TYPESAFE_API_KEY` is the credential boundary; credentials are never accepted in `config.toml`, receipts, or logs.

## Modes

- `deterministic`: no semantic provider invocation.
- `typesafe`: TypeSafe evidence may affect only explicitly automatable decisions after Agent-Workflow policy and confidence checks.
- `comparative`: TypeSafe is evaluated, deterministic control remains applied, and the counterfactual candidate is captured through the neutral comparative-eval capability.

Current live semantic decisions are only `routing.task_class`, `routing.interaction_required`, and `routing.semantic_risk`. Skill evaluation is not a runtime routing decision and is not reintroduced by this integration.
