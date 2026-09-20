# Semantic Decision Coverage

Agent-Workflow separates deterministic lifecycle authority from bounded semantic advice.
A decision belongs in `agent_workflow.decisions.DECISIONS` only when it is a live host
runtime boundary with a real deterministic control value. Registration is not a catalog
of every semantic question a plugin can answer.

## Runtime comparative boundaries

| Decision | Deterministic control | TypeSafe shadow | Authority |
| --- | --- | --- | --- |
| `routing.task_class` | deterministic router classification | yes | host policy |
| `routing.interaction_required` | deterministic router interaction flag | yes | host policy |
| `routing.semantic_risk` | deterministic risk projection | yes | deterministic in comparative mode; non-automatable |

All three are entered through `advise_routing_with_policy()` and then
`execute_decision_set()`. In comparative mode, reaching this boundary invokes the
configured semantic provider. Provider failure, uncertainty, invalid output, or policy
rejection is represented in the decision receipt; it must not silently acquire lifecycle
authority.

## Skill semantic evaluation is not a runtime decision boundary

The TypeSafe plugin also exposes `evaluate-skill`, whose question set includes behavior
support, completeness, and actionability. These are useful semantic evaluation dimensions
for explicit plugin use and comparative benchmark datasets, but they are **not** registered
host decisions.

`skill.behavior_satisfied` has a deterministic regex control in the release/evaluation
corpus, but that check is a static release audit rather than a normal workflow runtime
choice. `skill.completeness` and `skill.actionability` have no independent deterministic
host control. Treating those questions as registered comparative decisions would therefore
create false coverage and, for two dimensions, a comparison without a valid baseline.

If a future workflow feature needs one of these as a live decision, add the host control
and production call site first, then register the decision and provider support together.

## Deterministic-only authority

The following classes remain outside semantic-provider dispatch unless an explicit future
design changes their role:

- lease/ownership and duplicate-execution prevention;
- process/worker state and executor identity;
- schema, path, permission, and authorization checks;
- lifecycle transitions, retry eligibility, and recovery bookkeeping;
- required receipt/evidence existence and persistence;
- review/acceptance gates and final acceptance authority;
- command exit status and other directly observable execution facts.

Semantic advice may later help classify evidence, failures, or remediation choices, but such
advice must remain distinct from these deterministic gates.

## Coverage invariant

For every entry in `DECISIONS`:

1. a production host path supplies an independent deterministic control value;
2. the path enters `execute_decision_set()` rather than calling a semantic plugin directly;
3. a provider advertising the decision can be invoked automatically when its decision mode is active;
4. comparative mode keeps the control authoritative and records candidate/fallback evidence; and
5. registration, provider support, and the production call site are changed together.

A plugin may expose additional explicit advisory/evaluation commands without advertising
those questions as host decision-provider coverage.
