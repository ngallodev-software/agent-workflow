# Agent-Workflow prompt-pack continuation — open follow-ups

## Scope

This document retains only unresolved follow-ups from the OSINT Suite
`osint-suite-repo-simplification-20260829` prompt-pack continuation.
Resolved and verified Agent-Workflow implementation defects have been removed.

## Open follow-ups

### Full external-host launch matrix

The repaired external launcher successfully reached `running` from a
non-terminal host. A disposable end-to-end execution under both a real TTY and
non-TTY host remains a release-retest item. It should prove the worker receives
and acknowledges persisted steering, then publishes revision-bound completion.

### Dirty-source delegation diagnostic

`delegate --repo` correctly refuses a dirty source checkout by default. When
both `--base-ref` and `--dest` are explicit, the error should explain that
`--allow-dirty` creates the requested clean worktree from the immutable base.
Keep the protective default; improve only the diagnostic.

### Adjacent Codex gateway model-catalog failure

External launches still log:

```text
failed to decode models response: missing field `truncation_policy`
```

The worker can continue, but the raw catalog body is excessively large and
obscures executor logs. This is outside Agent-Workflow lifecycle authority.
Normalize `truncation_policy` for every gateway model record and bound/redact
raw diagnostic bodies.
