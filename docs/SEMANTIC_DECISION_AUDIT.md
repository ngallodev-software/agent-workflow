# Semantic Decision Audit — 0.11.6

This audit distinguishes live semantic runtime boundaries from deterministic authority, observed facts, open-ended coding-model work, and **candidate bounded decisions** being studied for future Jev/TypeSafe use.

## Live result

The production TypeSafe runtime surface remains intentionally limited to routing:

| Area | Classification | TypeSafe action |
| --- | --- | --- |
| task class | bounded semantic decision | registered; comparative shadow |
| interaction required | bounded semantic decision | registered; comparative shadow |
| semantic risk | bounded semantic evidence | registered; no authority |
| explicit role, executor/model, graph readiness | instruction or deterministic policy/state | deterministic only |
| worker health, process state, retry bookkeeping | observable fact/lifecycle state | deterministic only |
| verification result, scoring arithmetic | directly observable/deterministic evaluation | deterministic only |
| review and acceptance | ordered evidence/authorization gates | deterministic authority |
| source/schema/path/permission/hash facts | deterministic invariant | deterministic only |

When no role is supplied, the scheduler enters the registered routing boundary and dispatches the three decisions through the shared decision execution path. Explicit roles remain authoritative instructions.

No BM3 candidate described below is a production decision merely because it appears in this audit.

## Why the audit expanded

Round 2 showed that `agent-workflow-full/v1` used materially more wall time and provider tokens than `raw-direct/v1`, with the largest wall-time deltas in implementation and analyze/plan. Round 2 did not score quality.

That evidence creates a new optimization question:

> Which decisions currently left to a general-purpose coding model, or handled by brittle deterministic interpretation of messy context, are actually finite semantic decisions that Jev can answer more efficiently?

The target is not “replace deterministic code with AI.” The target is “use the cheapest reliable decision mechanism at each boundary.”

## Candidate semantic seams for BM3/follow-up study

These are **shadow/comparative research candidates**, not registered production seams.

| Candidate | Likely primitive | Why it may fit | Deterministic consumer remains |
| --- | --- | --- | --- |
| verification path selection | Choice | finite authorized test/check catalog | command authorization/execution/result |
| review-attention triage | Choice / Score | prioritize bounded concern categories | review gate and disposition |
| evidence/context relevance | Score / Choice | rank host-enumerated evidence bundles | context construction and size limits |
| remediation classification | Choice | map messy diagnostics to bounded remediation class | retry/action eligibility |
| planning strategy/depth | Choice | decide whether open-ended planning is warranted | actual plan/code generation |
| additional model pass required | Noul | bounded proposition after deterministic evidence | required verification/review gates |
| semantic escalation need | Noul / Score | identify uncertainty/consequence | user/host authorization |
| delegation metadata/role hint | Choice | choose among configured logical options | explicit role and runtime policy |

See [BM3_TYPESAFE_JEV_OPTIMIZATION_AUDIT.md](BM3_TYPESAFE_JEV_OPTIMIZATION_AUDIT.md) for the full Round 2 evidence, primitive guidance, timing plan, and promotion criteria.

## TypeSafe implementation pattern

A new semantic seam should follow:

```text
StateProjector
  -> versioned bounded QuestionSet
  -> TypeSafe/Jev Choice | Noul | Score
  -> normalized DecisionReceipt
  -> application-owned DecisionPolicy
  -> deterministic consumer
```

State projection must be bounded, provenance-aware, redacted, and must not include the deterministic answer during comparative evaluation. TypeSafe transport/client code does not own business thresholds.

Confidence is evidence, not correctness or authorization. Noul means `P(true)`. Score represents ordered degree/intensity. Choice selects one bounded candidate and must be locally revalidated.

## Full request/response audit

Agent-Workflow 0.11.5+ can record `agent-workflow/typesafe-api-call/v2` JSONL with the redacted logical request, exact question bodies, raw HTTP exchange when exposed by the SDK, normalized result, model/SDK identity, request hash, and duration.

BM3 preserves that private evidence because candidate-seam quality cannot be judged without checking:

- whether the projected state contains the right facts;
- whether irrelevant/repeated context was supplied;
- whether the question criteria are correctly bounded;
- whether the primitive is appropriate;
- whether an apparent disagreement is semantic failure or policy/threshold error.

Raw request/response bodies remain private evidence.

## Coverage invariant

For every entry in the production `DECISIONS` registry:

1. a real production host path supplies a control value or explicitly defined baseline;
2. the path uses the shared decision execution boundary;
3. provider support and the consumer are wired together;
4. comparative mode records control/candidate evidence without changing deterministic authority;
5. failure, uncertainty, no-match, and policy rejection are explicit;
6. registry/provider/receipt/tests/docs change together.

Do not register a candidate merely to increase TypeSafe call volume.

## Promotion criteria

A BM3/follow-up candidate may become a production seam only when:

1. the output taxonomy is finite and stable;
2. projected state is sufficient, bounded, and auditable;
3. the result has a concrete deterministic consumer;
4. uncertainty and fallback behavior are explicit;
5. representative comparative evidence shows acceptable semantic reliability;
6. calibrated application policy owns thresholds;
7. moving the decision reduces general-model context/time/retries or improves decision quality enough to matter;
8. lifecycle, authorization, verification, review, and acceptance authority remain deterministic.
