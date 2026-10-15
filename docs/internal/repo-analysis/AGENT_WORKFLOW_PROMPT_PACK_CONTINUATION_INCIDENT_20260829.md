# Agent-Workflow prompt-pack continuation — follow-ups and resolutions

## Scope

This document tracks unresolved follow-ups and resolutions from the OSINT Suite
`osint-suite-repo-simplification-20260829` prompt-pack continuation.

## Follow-ups

### Durable output-capture exhaustion — RESOLVED

TASK-002 reached a terminal `output_capture_exhausted` failure even though its
partial handoff contained useful implementation evidence and focused checks
had passed. This is a distinct Agent-Workflow reliability issue: bounded
capture is correctly fail-closed, but a worker producing oversized diagnostic
output could make a valid completion handoff fail. The runner now preserves
bounded capture and records truncation warnings without treating them as fatal
when the completion handoff is valid. The acceptance regression
`test_valid_completion_survives_bounded_auxiliary_output` covers this case.

The incident coincided with the adjacent Codex model-catalog decode failure
below, whose unbounded raw response likely contributed to capture exhaustion;
the causal relationship should be confirmed with measured output sizes.

### Full external-host launch matrix — PARTIALLY RESOLVED

The repaired external launcher successfully reached `running` from a
non-terminal host. The pipe/PTY acceptance tests now cover durable start and
completion behavior in both host modes. A matrix proving persisted steering
acknowledgement and revision-bound completion through an external host remains
open.

### Dirty-source delegation diagnostic — RESOLVED

`delegate --repo` correctly refuses a dirty source checkout by default. When
both `--base-ref` and `--dest` are explicit, the error should explain that
`--allow-dirty` creates the requested clean worktree from the immutable base.
The protective default remains, and the diagnostic now explains that behavior.

### Adjacent Codex gateway model-catalog failure

External launches still log:

```text
failed to decode models response: missing field `truncation_policy`
```

The worker can continue, but the raw catalog body is excessively large and
obscures executor logs. This is outside Agent-Workflow lifecycle authority.
Normalize `truncation_policy` for every gateway model record and bound/redact
raw diagnostic bodies.
