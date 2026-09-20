# TypeSafe comparative evaluation

This is an opt-in evidence projection. Agent-Workflow remains authoritative;
the candidate is never applied to routing, execution, completion, review, or
acceptance.

```python
from agent_workflow.comparative_eval_runtime import EvidenceStore

# Comparative routing capture is performed by SchedulerService when
# decision_policy.mode = "comparative"; it reuses the already-computed candidate.

# Inspect persisted observations through EvidenceStore or `agent-workflow decision report`.
```

Static cases must use a frozen dataset and an independent oracle. Normal-usage
capture stores hashes and bounded metadata, never raw task text or secrets.
Candidate failures are isolated; control execution remains authoritative.
SQLite rows are immutable and idempotent by observation ID or
`(observation_id, outcome_kind)`. Reports reject mixed feature, mode, or cohort
identities. Shadow outcomes are descriptive, not causal, and require separate
review/acceptance evidence before any guarded experiment.
