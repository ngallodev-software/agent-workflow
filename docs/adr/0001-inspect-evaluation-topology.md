# ADR 0001: Inspect evaluation topology

- Status: accepted
- Date: 2026-07-17

## Context

`agent-workflow` owns host worktrees, tmux lifecycle, and durable run evidence. Inspect AI already owns evaluation datasets, sandboxes, model routing, transcripts, scorers, logs, and comparison execution. `inspect_swe` already provides complete Codex CLI and Claude Code agents using Inspect's sandbox bridge.

Installing `agent-workflow`, Python, and tmux inside every evaluation container would create a second lifecycle stack and duplicate private `inspect_swe` setup, bridge, retry, and event-handling logic. A host process also cannot safely manipulate opaque paths inside an Inspect sandbox.

## Decision

Compose at the orchestration boundary:

```text
host agent-workflow session
  -> optional Inspect runner
    -> Inspect Docker sandbox
      -> inspect_swe codex_cli() or claude_code()
        -> Inspect sandbox_agent_bridge()
```

- Inspect and telemetry dependencies remain optional; core contract validation uses the small established `jsonschema` dependency.
- Inspect dependencies live behind the `eval` optional extra and initially use pinned versions.
- Reuse public `inspect_swe` Codex and Claude agents as whole adapters. Do not copy their private installers or bridge internals.
- Inspect owns sandbox creation, model API routing, transcripts, retries, scoring, and eval logs.
- The evaluated repository is copied or unpacked into the sandbox; the host worktree, home directory, Docker socket, credentials, and outer run state are never mounted.
- Evaluator-only oracles stay on the host and are resolved only after agent execution.
- Before sandbox teardown, export a binary Git patch plus a sealed artifact bundle containing repository state, completion data, tool versions, and hashes.
- The outer host session stores the Inspect log reference and exported bundle; its target worktree intentionally remains unchanged.

## Initial compatibility pins

- `inspect-ai==0.3.247`
- `inspect-swe==0.2.66`
- Codex CLI `0.144.5`
- Claude Code `2.1.212`
- Docker sandbox required for agent-writing evaluations

Pins are upgraded deliberately with adapter contract tests and live two-executor smoke evaluation.

## Consequences

- Core installation remains small and offline-capable.
- Inspect provides the evaluation engine and UI; `agent-workflow` adds only contracts, evidence collectors, receipts, and thin adapters.
- Model calls appear in Inspect transcripts and accounting.
- Patch/evidence custody requires explicit export and hash verification before container cleanup.
- Inspect API changes are isolated to optional adapter modules.

## Rejected alternatives

- **Run full agent-workflow inside each sandbox:** duplicates lifecycle, tmux, Python, XDG state, and adapter setup.
- **Host agent-workflow controls sandbox paths:** unsupported isolation boundary and fragile artifact custody.
- **Reimplement Inspect scheduling/scoring/log viewer:** unnecessary platform duplication.
