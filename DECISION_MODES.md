# Decision modes and semantic providers

Agent-Workflow owns the decision registry, deterministic control, thresholds, fallback, final application policy, and receipts. The built-in modes are:

- `deterministic` — control only, no semantic call;
- `typesafe` — optional TypeSafe evidence may be applied only on explicitly automatable seams;
- `comparative` — the same TypeSafe candidate is captured against deterministic control while control remains authoritative.

TypeSafe is an optional feature rather than a plugin:

```bash
python -m pip install 'agent-workflow[typesafe]'
export TYPESAFE_API_KEY='...'
```

```toml
[semantic]
provider = "typesafe"

[semantic.typesafe]
# model = "jev-latest"
# api_call_log = "~/.local/state/agent-workflow/typesafe-api-calls.jsonl"

[decision_policy]
mode = "comparative"
profile = "routing-v1"

[decision_profiles.routing-v1."routing.task_class"]
disposition = "shadow"
minimum_confidence = 0.80
```

`--decision-mode` and `--decision-profile` override policy for one invocation. `--no-plugins` affects external plugins only and does not alter built-in semantic policy.

Semantic transport failure, no-match, uncertainty, and policy rejection remain distinct in `agent-workflow/decision-execution-receipt/v1`. TypeSafe credentials are read only from `TYPESAFE_API_KEY`.

## Comparative evidence

`comparative` requires the neutral `agent-workflow-comparative-eval` optional dependency. Agent-Workflow records the already-computed control/candidate pair without a second TypeSafe call and persists `comparative-eval.sqlite` in the workflow coordinator directory.
