# Semantic Decision Audit — 0.11.0

This audit traces production host paths that might look like candidates for TypeSafe
semantic assistance, distinguishing real decision boundaries from observed facts,
deterministic lifecycle rules, explicit judgment, and evaluation-only questions.

## Result

The live TypeSafe runtime surface is intentionally limited to routing. No additional
0.11.0 production boundary should be promoted merely to increase TypeSafe call volume.
The next boundary requires an independent control and a concrete consumer.

| Area | Classification | TypeSafe action |
| --- | --- | --- |
| task class | bounded semantic decision | registered; comparative shadow |
| interaction required | bounded semantic decision | registered; comparative shadow |
| semantic risk | bounded semantic evidence | registered; no authority |
| explicit role, executor/model, graph readiness | instruction or deterministic policy/state | deterministic only |
| worker health, remediation, retry, completion, evaluation | observable facts or lifecycle/evaluation gates | deterministic only |
| review and acceptance | explicit action and ordered gates | no automatic TypeSafe authority |
| skill behavior/completeness/actionability | static or explicit evaluation | not runtime decisions |

When no role is supplied, the scheduler enters `advise_routing_with_policy()` and
dispatches the three registered routing decisions through `execute_decision_set()`.
Explicit roles remain authoritative instructions and correctly skip routing comparison.

## Coverage invariant

`tests/test_decision_boundary_coverage.py` parses production call sites and requires
literal IDs passed to `execute_decision_set()` to equal the host `DECISIONS` registry.
The TypeSafe plugin separately advertises only those routing IDs. This catches both
registered-but-unwired and wired-but-unregistered semantic decisions.

## Future boundary criteria

Add a runtime semantic decision only when it requires semantic judgment, has an
independent deterministic control, a concrete consumer, a bounded output taxonomy,
an explicit fallback, comparative shadow support, and synchronized registry/provider/
receipt/test/documentation changes.
