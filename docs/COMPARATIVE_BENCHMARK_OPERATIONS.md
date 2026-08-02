# Comparative benchmark operations


## Scoring interpretation

The commands in this guide operate the currently shipped v1 suite. Existing v1 reports must be interpreted according to the shipped evaluator, including equal-share check weighting within dimensions. For the exact task, checks, points, human rubric, guardrails, and known discrepancies, read [COMPARATIVE_BENCHMARK_EXPLAINED.md](COMPARATIVE_BENCHMARK_EXPLAINED.md). The corrected major-version work is tracked in [COMPARATIVE_BENCHMARK_CORRECTION_BACKLOG.md](COMPARATIVE_BENCHMARK_CORRECTION_BACKLOG.md). Do not compare v1 and corrected-version cohorts as though their scores have identical meaning.

This guide runs `priority-picker-v1` with subscription-backed provider CLIs by default. API-key profiles are optional and must be selected explicitly.

## Export and inspect the suite

```bash
agent-workflow benchmark suite-export /tmp/priority-picker-v1
agent-workflow benchmark validate \
  /tmp/priority-picker-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-v1/executors/codex-subscription.json
```

The exported suite includes:

- `executors/codex-subscription.json` and `executors/claude-subscription.json`;
- optional `codex-api-key.json` and `claude-api-key.json` profiles;
- development, internal, and publication operating policies;
- a development visual-runtime lock and publication container/sealing assets.

## Authenticate through the provider subscription

Authenticate with the provider CLI outside the benchmark. Then run the read-only preflight:

```bash
agent-workflow benchmark auth-check \
  /tmp/priority-picker-v1/executors/codex-subscription.json

agent-workflow benchmark auth-check \
  /tmp/priority-picker-v1/executors/claude-subscription.json
```

A subscription profile deliberately fails when its provider API-key or access-token environment variable is present. Unset the variable or select the corresponding explicit API profile. The benchmark never silently changes billing paths.

## Check readiness before creating worktrees

Development smoke test:

```bash
agent-workflow benchmark readiness \
  /tmp/priority-picker-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-v1/executors/codex-subscription.json \
  --policy /tmp/priority-picker-v1/policies/development.json
```

Internal cohort:

```bash
agent-workflow benchmark readiness \
  /tmp/priority-picker-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-v1/executors/codex-subscription.json \
  --policy /tmp/priority-picker-v1/policies/internal.json
```

Readiness checks authentication, visual runtime identity, repetition thresholds, subscription-default policy, and retry isolation without modifying the target repository.

## Create the frozen fixture and plan a cohort

```bash
agent-workflow benchmark fixture-create \
  /tmp/priority-picker-v1/benchmark-spec.json \
  /tmp/priority-picker-fixture

agent-workflow benchmark plan \
  /tmp/priority-picker-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-v1/executors/codex-subscription.json \
  --policy /tmp/priority-picker-v1/policies/internal.json \
  --repo /tmp/priority-picker-fixture \
  --run-id codex-priority-picker-internal
```

The policy supplies the repetition and retry counts. Command-line overrides, when permitted for development, are recorded as policy overrides rather than silently replacing the sealed profile.

## Execute and review

```bash
agent-workflow benchmark run codex-priority-picker-internal
agent-workflow benchmark status codex-priority-picker-internal
agent-workflow benchmark review codex-priority-picker-internal --reviewer reviewer-01
```

Internal claims require two completed blinded reviews. Publication claims require three. Submit each generated review template with `benchmark review --input` and then verify the consolidated run:

```bash
agent-workflow benchmark report codex-priority-picker-internal
agent-workflow benchmark verify codex-priority-picker-internal
agent-workflow benchmark cleanup codex-priority-picker-internal
# Add --remove-worktrees only when the arm source trees are no longer needed.
```

Cleanup preserves arm worktrees by default, keeping the built apps viewable. Use
`--remove-worktrees` for explicit removal after verified consolidation; the
coordinator worktree and `benchmarks/runs/<run-id>` evidence remain preserved.

## Optional API authentication

To run an explicitly metered cohort, select an API executor profile and supply the named credential only in the process environment:

```bash
OPENAI_API_KEY=... agent-workflow benchmark readiness \
  /tmp/priority-picker-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-v1/executors/codex-api-key.json \
  --policy /tmp/priority-picker-v1/policies/internal.json
```

Do not compare or pool a subscription cohort with an API-key cohort. Authentication mode and billing semantics are part of the sealed executor identity.

## Publication visual runtime

Build and publish the supplied browser image, resolve its immutable registry digest, run the container, and seal the runtime lock from inside that exact image:

```bash
agent-workflow benchmark runtime-seal \
  /suite/visual-runtime-lock.json \
  /suite/visual-runtime-lock.publication.json \
  --container-image registry.example/agent-workflow-benchmark@sha256:<64-hex-digest>

agent-workflow benchmark runtime-attest \
  /suite/visual-runtime-lock.publication.json \
  --claim-level publication
```

Pass the sealed lock to both `readiness` and `plan` using `--runtime-lock`. A tag-only image reference, unresolved font, mismatched browser binary, or host runtime fails publication readiness.

## Failure interpretation

- Authentication failure: repair the selected provider session; do not switch authentication mode mid-cohort.
- Infrastructure failure: the runner may use the one preplanned fresh pair retry.
- Task failure or low score: terminal benchmark evidence; no retry.
- Interrupted pair: discard both arms and use the fresh paired attempt.
- Missing provider usage: remains null and may invalidate the configured usage guardrail.
- Missing human review: report remains `awaiting_human_review`; no final composite or winner.
