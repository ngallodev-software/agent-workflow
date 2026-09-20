# TypeSafe semantic routing

Read this reference only when Agent-Workflow semantic decision modes, TypeSafe routing evidence, comparative evaluation, or TypeSafe receipts are relevant. Normal deterministic lifecycle work does not require it.

## Application boundary

Agent-Workflow owns routing policy and all lifecycle authority. TypeSafe is an optional built-in provider for three bounded routing judgments only:

- `routing.task_class` — Choice over implementation, diagnosis, review, documentation, or other.
- `routing.interaction_required` — Noul probability that a material user decision or authorization is missing.
- `routing.semantic_risk` — Score on the ordered consequence of acting on an incorrect semantic interpretation.

TypeSafe does not own leases, duplicate-execution prevention, executor facts, authorization, lifecycle transitions, required evidence, review, acceptance, or irreversible actions. Never use semantic evidence to bypass those deterministic authorities.

## Input contract

The built-in provider projects `routing-state/v2`. Supply bounded evidence that materially affects routing:

- `observed.request_text`: the actual task/request text, not a paraphrased control answer;
- `observed.declared_metadata`: caller-supplied task metadata;
- `observed.source_refs`: durable locators when available;
- `deterministic_context`: allowed routing classes and authority facts that define the decision boundary.

Keep observed facts distinct from deterministic context. Do not include the deterministic routing result in the TypeSafe state during comparative evaluation; that anchors the candidate arm and invalidates the comparison. Do not add repository contents, secrets, or unrelated context merely to make the prompt larger. If the bounded state does not contain enough evidence for a meaningful semantic judgment, preserve uncertainty or fall back instead of inventing context.

## Primitive interpretation

Treat SDK outputs as evidence, not decisions.

### Choice

`evidence_result` is the selected bounded semantic label. Inspect `semantic.distribution` and `semantic.confidence` when evaluating uncertainty. Confidence describes concentration of the returned distribution; it is not authorization, correctness, or permission to automate. Agent-Workflow maps provider labels to its routing classes before policy use.

### Noul

`evidence_result` and `semantic.probability` are `P(proposition=true)`. They are not generic confidence values. Values near 0.5 are genuine uncertainty. Application policy may map sufficiently extreme probabilities to `true` or `false`; otherwise `policy_candidate_result` remains null.

### Score

`evidence_result` is the expected position on the question's ordered rubric. It is not an exact physical measurement. Retain the level distribution and confidence. A diffuse distribution can still be useful comparative evidence even when policy rejects it for automation.

## Receipt layers

Decision receipt v2 deliberately separates:

1. `control_result` — deterministic control arm;
2. `evidence_result` — raw normalized TypeSafe semantic evidence;
3. `policy_candidate_result` — evidence after Agent-Workflow threshold/mapping policy;
4. `applied_result` — authoritative value actually used.

In `comparative` mode, the deterministic result remains applied even when the semantic candidate is policy-eligible. In `typesafe` mode, a candidate can affect behavior only for a decision explicitly marked automatable and only after application policy accepts it. `routing.semantic_risk` is not automatable.

Never interpret `policy_candidate_result = null` as “TypeSafe returned no evidence.” Check `semantic.status` and `evidence_result`. A null policy candidate can simply mean semantic uncertainty.

## Thresholds and calibration

Thresholds are Agent-Workflow policy, not SDK semantics. Do not infer a production threshold from a TypeSafe confidence value. Calibrate thresholds from representative Agent-Workflow cases and retain raw distributions/probabilities so disagreement, false-accept/false-reject, escalation coverage, and calibration can be measured.

## Failure handling

Missing SDK/key, service failure, invalid contracts, no-match, and semantic uncertainty must remain explicit in receipts. The deterministic route remains available. Do not retry an identical semantic request merely to seek a different opinion.

## Live qualification evidence

The 2026-09-20 live qualification exercised `routing-state/v2` / `routing/v2` with the hosted provider. Choice routing agreed with deterministic implementation/review/diagnosis cases; Noul and Score returned useful uncertainty; receipt v2 preserved raw evidence while policy rejected uncertain candidates. Treat that as integration qualification, not threshold calibration.
