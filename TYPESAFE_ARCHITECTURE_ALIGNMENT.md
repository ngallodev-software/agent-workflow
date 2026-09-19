# TypeSafe architecture alignment

This implementation follows the attached `typesafe-impl-internal` skill boundary:

```text
projected application state
        -> plugin semantic provider
        -> raw typed semantic evidence
        -> Agent-Workflow DecisionPolicy
        -> existing deterministic application behavior
```

## Host authority

Agent-Workflow owns stable decision IDs, deterministic control values, thresholds, fallback, application-policy composition, lifecycle/review/acceptance authority, and `agent-workflow/decision-execution-receipt/v1`.

`deterministic` is the only built-in decision mode. Optional plugins may advertise additional modes and semantic providers, but cannot replace deterministic recovery or bypass host policy.

## TypeSafe provider

`agent-workflow-typesafe-ai` advertises the `typesafe` and `comparative` modes plus a `typesafe` semantic provider. The comparative mode also advertises the generic `capture_comparison` capability, which causes the host to persist shared-library observations without a second TypeSafe call. The provider batches the routing questions in one TypeSafe request and returns provider-neutral evidence. It does not own automation thresholds or final routing.

## Mode semantics

- `deterministic`: no semantic provider invocation.
- `typesafe`: semantic evidence may be consumed by the Agent-Workflow policy on explicitly automatable seams. Failures/uncertainty/no-match fall back to deterministic control.
- `comparative`: semantic evidence is evaluated but the deterministic control result remains authoritative; the same host routing policy computes the counterfactual candidate route.

Per-decision profiles may tighten thresholds or downgrade disposition to `shadow` / `advisory`. High-consequence `routing.semantic_risk` remains non-automatable in the current registry.

## Benchmarking

The historical comparative benchmark subsystem is optional product capability rather than host authority. It has therefore moved to the `agent-workflow-benchmark` plugin. Core retains generic sealed-run evaluation, deterministic scoring/review/lifecycle authority, and generic evaluation primitives.
