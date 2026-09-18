# TypeSafe comparative evaluation

This is an opt-in evidence projection. Agent-Workflow remains authoritative;
the candidate is never applied to routing, execution, completion, review, or
acceptance.

```python
from agent_workflow.typesafe_eval_runtime import EvidenceStore, ShadowCapture

store = EvidenceStore("comparison.sqlite3")
capture = ShadowCapture(store, enabled=True, sample_rate=0.1)
capture.capture(feature_id="routing-advice/v1", identity={"feature_version": "v1"},
               source_input=bounded_input, projected_input=projection,
               control=run_control, candidate=run_candidate)
report = store.report()
```

Static cases must use a frozen dataset and an independent oracle. Normal-usage
capture stores hashes and bounded metadata, never raw task text or secrets.
Candidate failures are isolated; control execution remains authoritative.
SQLite rows are immutable and idempotent by observation ID or
`(observation_id, outcome_kind)`. Reports reject mixed feature, mode, or cohort
identities. Shadow outcomes are descriptive, not causal, and require separate
review/acceptance evidence before any guarded experiment.
