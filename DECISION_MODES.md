# Decision modes and semantic providers

Agent-Workflow owns the decision registry, deterministic control results, thresholds, fallback policy, final application policy, and receipts. `deterministic` is the only built-in mode. Optional plugins may advertise semantic decision providers and named modes through the public plugin descriptor.

Configuration example:

```toml
[plugins]
enabled = ["agent-workflow-typesafe"]

[decision_policy]
mode = "comparative"
profile = "routing-v1"

[decision_profiles.routing-v1."routing.task_class"]
disposition = "shadow"
minimum_confidence = 0.80
```

`--decision-mode` and `--decision-profile` override configuration for one CLI invocation. `--no-plugins` forces deterministic recovery unless an explicit plugin mode was also requested, which is rejected as contradictory.

Plugin modes are discovered only from installed **enabled** plugins. A plugin mode cannot replace the built-in deterministic mode. Semantic transport failure, no-match, semantic uncertainty, and policy fallback remain distinct in `agent-workflow/decision-execution-receipt/v1`.

## Comparative evidence

A plugin-advertised mode may set `capture_comparison=true`. Agent-Workflow then requires the neutral `agent-workflow-comparative-eval` library, records the already-computed control/candidate pair without making a second semantic call, and persists evidence in the workflow coordinator directory as `comparative-eval.sqlite`. Terminal child completion is joined as a separate immutable outcome. Inspect it with:

```bash
agent-workflow decision report /path/to/workflow-run/comparative-eval.sqlite
```

The capability is discovered from the enabled plugin mode descriptor; core does not hardcode a `comparative` provider or TypeSafe mode name.
