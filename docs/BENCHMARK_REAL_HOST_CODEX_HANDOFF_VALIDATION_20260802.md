# Benchmark real-host Codex handoff validation

Date: 2026-08-02  
Baseline: `agent-workflow` 0.7.9 benchmark enhancements through checkpoint 10

## Handoff contents

The complete source tree includes the review-only prompt pack:

`prompt-packs/benchmark-real-host-release-candidate-gate/`

The pack contains four phases, thirteen structured review/gate tasks, exact command guidance, evidence templates, tmux/process monitoring utilities, a machine-readable 100-point evaluation manifest, an evidence schema, and an executable final evaluator.

## Source reconciliation

The canonical backlog was corrected so BENCH-CORR-001 through BENCH-CORR-010 no longer appear as unimplemented/blocked. They are marked `in-review`, reflecting that implementation and local deterministic evidence exist while independent real-host/provider/browser gates remain open. The new handoff pack is documented as review-only and claims no backlog ownership.

## Validation completed before packaging

```text
python prompt-packs/benchmark-real-host-release-candidate-gate/evals/evaluate_handoff.py --self-test
valid: true; checks: 27; points: 100
```

```text
PYTHONPATH=src python -m agent_workflow pack validate \
  prompt-packs/benchmark-real-host-release-candidate-gate
valid: true; phases: 4; tasks: 13
```

```text
PYTHONPATH=src python scripts/audit-release-assets.py
release assets: valid
```

```text
PYTHONPATH=src pytest -q tests/invariants
291 passed in 20.31s
```

```text
PYTHONPATH=src pytest -q tests/release/test_distribution.py
6 passed in 12.59s

PYTHONPATH=src pytest -q tests/release/test_documentation_sync.py
4 passed in 1.24s

PYTHONPATH=src pytest -q tests/release/test_release_installers.py
4 passed in 3.47s
```

The evaluator was also tested against a complete synthetic evidence bundle, producing `accepted` at 100/100, and against the incomplete template, producing a nonzero `blocked` result with all missing mandatory checks identified.

## Remaining external gates

This archive does not claim the following were executed locally:

- authenticated Codex subscription benchmark execution;
- authenticated Claude subscription benchmark execution;
- direct same-window tmux pane observation;
- real-provider cancellation/no-orphan observation;
- real-provider compact timing below three minutes;
- live browser inspection and independent blinded human scoring;
- publication runtime image/digest/font attestation.

Those gates are the purpose of the bundled Codex prompt pack and cannot be marked complete without its required evidence.
