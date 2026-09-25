# Changelog

## 0.11.10

- Preserve Choice/Noul/Score probability evidence through the comparative persistence boundary.
- Emit separate neutral observations for `routing.task_class`, `routing.interaction_required`, and `routing.semantic_risk`.
- Persist one shared provider-request record for each batched TypeSafe call so latency/token/cost accounting is not triple-counted.
- Add request identity, projector version, and provider usage to decision evidence/receipts.
- Centralize receipt-to-comparative projection so runtime capture and benchmark studies use the same semantics.
- Require `agent-workflow-comparative-eval==0.2.0` for comparative mode.


- Integrate the Agent-Workflow-specific TypeSafe routing provider into core as an optional `typesafe` extra, using official SDK `Choice`, `Noul`, and `Score` primitives. The former `agent-workflow-typesafe-ai` plugin/package is retired; generic plugin support remains available for independent extensions.

