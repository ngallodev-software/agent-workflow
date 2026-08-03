# Delegation runbook

## Baseline preflight

Use the 0.7.9 repository root and one isolated worktree per writable ticket. Record:

```bash
pwd
git status --short
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
cat VERSION
python3 --version
```

Verify the ownership map in `references/LOCATION_DISCOVERY_AND_MAPPING.md`. If a listed owner moved after 0.7.9, record the new dedicated owner and do not reintroduce the old path.

Run the baseline checks available in the worktree:

```bash
python3 -m pytest -q \
  tests/invariants/test_comparative_benchmark_contracts.py \
  tests/invariants/test_comparative_benchmark_operating_policy.py \
  tests/acceptance/test_comparative_benchmark_journey.py
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/comparative-benchmark-scoring-corrections
```

Use the source environment's public CLI when an installed `agent-workflow` is not yet available; record which surface was exercised.

## Launch and parallelism

Phase 0 tickets may analyze in parallel but must converge on one accepted contract and efficiency policy. In phase 1, BENCH-CORR-002 lands before BENCH-CORR-003, BENCH-CORR-004, and BENCH-CORR-005 proceed in separate worktrees. Phase 2 tickets may run concurrently after their manifest dependencies. Phase 3 is sequential. Phase 4 integrates sequentially because pane topology, live review, and the compact suite share lifecycle boundaries; its final gate must use a separate review worktree and a real tmux host.

Never place two writable agents in one worktree. Integration is a separate reviewed action.

## Built-in feature and plugin discipline

- Benchmark behavior belongs in `src/agent_workflow/benchmarking/` and the dedicated CLI handler.
- Suite authoring belongs under `benchmarks/specs/`; installed export bytes belong under `src/agent_workflow/assets/benchmarks/`.
- Do not add benchmark hooks to `plugin_api.py` or `plugins.py`.
- Verify core benchmark commands with no enabled plugins and through `--no-plugins` recovery where applicable.
- A future distribution extraction is outside this pack and remains gated by ARC-004.

## Observe and recover

Use current `agent-workflow status`, `attach`, and `tail` behavior. Treat possible-stall signals as advisory. Inspect in the foreground before interruption. Retry into a fresh session/worktree and preserve lineage.

## Integration checks

After every merge:

- rerun exact contract arithmetic and schema validation;
- rerun relevant golden/mutation fixtures;
- compare the repository suite and installed asset mirror byte-for-byte;
- build/install/export the corrected suite when the phase reaches packaged behavior;
- verify old v1 reports remain readable and unchanged;
- verify mixed-version cohorts cannot declare a winner;
- verify benchmark commands do not require an enabled plugin;
- run `python3 scripts/audit-release-assets.py`;
- verify an installed run adds exactly two panes to the invoking window and reuses them;
- verify live applications remain reachable after automated scoring;
- verify the compact suite has one model phase below 180 seconds and exports byte-identically.

## Phase gate

At each phase boundary, run prompt-pack validation, the release audit, focused tests, and the smallest installed-product benchmark journey. Apply an independent reviewer. Use `templates/PHASE_GATE_REPORT.md` and explicitly accept or reject every ticket and each claim level affected.
