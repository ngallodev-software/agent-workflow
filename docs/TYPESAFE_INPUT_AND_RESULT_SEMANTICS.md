# TypeSafe input and result semantics

Agent-Workflow uses TypeSafe only for bounded semantic evidence. Deterministic lifecycle, authorization, executor/model allowlists, sealed evidence, and acceptance remain application-owned.

## State supplied to TypeSafe

The routing projector is versioned as `routing-state/v2`. It preserves epistemic categories rather than sending an unlabeled prompt blob:

- `observed.request_text`: the request text available at the routing boundary;
- `observed.declared_metadata`: caller-supplied routing metadata after bounded redaction;
- `observed.source_refs`: stable references, not source contents;
- `deterministic_context.routing_classes`: the finite meanings of the allowed Choice candidates;
- `deterministic_context.semantic_provider_authority`: explicitly records that the provider supplies evidence only;
- `deterministic_context.enforced_selection_remains_authoritative`: prevents semantic evidence from being confused with execution authority.

Do not send deterministic control results to TypeSafe as input. They would anchor the candidate arm and weaken comparative evidence. Add source evidence only when it materially changes the semantic judgment; preserve observed facts, deterministic derived facts, prior semantic inferences, user-authorized decisions, and policy as distinct fields.

The current state is sufficient for coarse task classification. It is sufficient for `interaction_required` only to the extent that the request/metadata actually contains the relevant authorization facts; missing external policy must not be guessed. Semantic risk is intentionally the consequence of acting on a wrong interpretation, not a substitute for deterministic security or lifecycle risk checks.

## Questions

`routing.task_class` is a Choice over a complete finite set with `other` as no-match. `routing.interaction_required` is one binary Noul proposition. `routing.semantic_risk` is one ordered Score dimension with behaviorally distinct low/moderate/high criteria. These follow the TypeSafe implementation skill's primitive guidance.

## Interpreting results

The SDK outputs are semantic evidence, not authority:

- Choice: `choice` is the raw selected candidate. `confidence` describes concentration of the Choice distribution; it is not correctness or permission. The full distribution is retained.
- Noul: `noul` is the probability of yes. Values near `0.5` are uncertainty, not medium severity. Thresholding into a boolean is application policy.
- Score: `score` is a probabilistic expectation along the ordered rubric. `confidence` and the level distribution describe uncertainty. Do not round the raw score or interpret it as an exact measurement.

Decision receipts therefore separate:

- `evidence_result`: the normalized raw semantic answer;
- `semantic.probability`, `semantic.confidence`, and `semantic.distribution`: uncertainty evidence;
- `policy_candidate_result`: the result after Agent-Workflow's threshold/mapping policy;
- `applied_result`: the authoritative result actually used.

A low-confidence Choice/Score or a Noul near 0.5 remains useful evidence even when `policy_candidate_result` is null. Comparative mode always keeps deterministic control authoritative.

## Thresholds and calibration

The current confidence thresholds are policy defaults, not validated production cutoffs. They must not be justified merely because a value such as `0.8` appears confident. Before guarded automation is expanded, calibrate on representative adjudicated cases and measure confusion/precision/recall, reliability, disagreement, coverage/escalation, paraphrase stability, latency, and cost.

The SDK/provider documentation is useful for interpreting the *shape* of each primitive result. Application calibration data must determine how those probabilities/confidences affect Agent-Workflow behavior.
