# agent-workflow 0.7.9 benchmark ownership map

This pack is rebased to the 0.7.9 repository. The relative paths below are the expected owners for the baseline. Before editing, verify that each path still exists and record any behavior-preserving move in the ticket completion report. Do not write through a compatibility facade when a dedicated owner exists.

| Functional surface | 0.7.9 path(s) | Authority/derivative | Required handling |
|---|---|---|---|
| CLI grammar | `src/agent_workflow/cli_parser.py` | Public command contract | Preserve parser/catalog/help behavior; add options only when required by the corrected contract. |
| Benchmark command dispatch | `src/agent_workflow/cli_handlers/benchmark.py` | Built-in feature adapter | Keep this thin; route behavior to the benchmarking service. |
| Public benchmark facade | `src/agent_workflow/benchmarking/__init__.py`, `service.py` | Built-in feature API | Preserve installed-product command behavior and typed errors. |
| Benchmark contracts | `src/agent_workflow/benchmarking/contracts.py`, `schemas/benchmark-*.schema.json` | Authority | Add versioned corrected contracts without mutating v1 schemas or receipts. |
| Planning/pair identity | `src/agent_workflow/benchmarking/planning.py`, `pairing.py`, `policy.py` | Authority | Preserve paired task identity, treatment separation, and sealed policy identity. |
| Execution/metrics/events | `runner.py`, `metrics.py`, `events.py`, `auth.py` | Authority/evidence | Do not combine scoring corrections with executor or authentication redesign. |
| Machine scoring | `src/agent_workflow/benchmarking/scoring.py` | Authority | Add explicit corrected-version weights and receipts; keep v1 interpretation available. |
| Human review | `src/agent_workflow/benchmarking/review.py` | Authority | Preserve blinded immutable review evidence and mapping privacy. |
| Visual runtime/capture | `src/agent_workflow/benchmarking/visual.py`, `runtime.py` | Authority/runtime | Keep publication runtime attestation separate from UI-quality points. |
| Reporting/statistics | `reporting.py`, `statistics.py` | Derived claims | Enforce version compatibility before cohort/winner calculations. |
| Consolidation | `consolidation.py` | Evidence authority | Preserve digest verification and immutable historical artifacts. |
| Repository benchmark source | `benchmarks/specs/priority-picker-v1/` | Source authoring surface | Preserve as immutable legacy input; create a new corrected-version sibling. |
| Installed benchmark mirror | `src/agent_workflow/assets/benchmarks/priority-picker-v1/` | Packaged derivative | Must remain byte-identical to the source suite for all exported files. |
| Benchmark package data | `pyproject.toml` package-data rule `agent_workflow = ["assets/**/*"]` | Packaging contract | Verify the corrected suite is present in built wheels and exportable outside the checkout. |
| Benchmark schemas | `schemas/benchmark-*.schema.json` | Installed data files | Add new schema versions; never reinterpret old schema identifiers. |
| Benchmark acceptance | `tests/acceptance/test_comparative_benchmark_journey.py` | Installed-product proof | Add corrected-suite export, calibration, review, report, verification, and cleanup journeys. |
| Benchmark invariants | `tests/invariants/test_comparative_benchmark_contracts.py`, `test_comparative_benchmark_operating_policy.py`, `test_cli_benchmark_handler_boundary.py` | Compact invariants | Cover arithmetic, versioning, policy, dispatch, and drift without duplicating the full journey. |
| Release drift | `scripts/audit-release-assets.py` | Release gate | Detect source/mirror, contract/docs, schema, backlog, and prompt-pack drift. |
| Benchmark docs | `docs/COMPARATIVE_BENCHMARK_SPEC.md`, `COMPARATIVE_BENCHMARK_IMPLEMENTATION.md`, `COMPARATIVE_BENCHMARK_OPERATIONS.md`, `COMPARATIVE_BENCHMARK_EXPLAINED.md` | Rationale/operations | Identify exact benchmark/scorer versions and distinguish intended from current behavior. |
| Man/help | `docs/man/agent-workflow.1`, `docs/COMMAND_REFERENCE.md`, parser help | Public docs | Generate or validate factual scoring tables from the authoritative contract. |
| Canonical backlog | `docs/BACKLOG.md` | Task authority | BENCH-CORR items have one active owner: this pack. |
| Pack registry | `docs/PROMPT_PACKS.md` | Active-pack index | Keep state and ownership synchronized. |
| Feature architecture | `docs/FEATURE_MODULE_ARCHITECTURE.md`, `docs/DECISIONS/DEC-009-FEATURE-MODULE-BOUNDARIES.md` | Distribution decision | Benchmark remains a built-in feature during this pack. |
| Trusted plugin API | `src/agent_workflow/plugin_api.py`, `plugins.py`, `docs/PLUGIN_API.md` | Separate extension boundary | Do not add scorer hooks or a second registry; only use digest-bound plugin resources if a separately approved future extraction requires them. |

## Plugin and extraction rule

The current plugin API registers explicitly enabled top-level commands and digest-bound package schema/asset resources. It does not register internal benchmark scorers, evaluators, policies, or review hooks. This pack must:

1. keep authority-bearing benchmark services in `agent_workflow.benchmarking`;
2. keep the CLI handler thin and plugin-independent;
3. separate pure contract parsing and evaluator result interpretation from process/worktree/evidence authority so later extraction is possible;
4. avoid modifying `plugin_api.py` or `plugins.py` merely to complete scoring corrections;
5. defer any distribution split to the evidence-gated `ARC-004` program after real first-party plugin evidence.

## Baseline contradictions to preserve as evidence

- `benchmark-spec.json` declares version `1.1.0`; `REQUIREMENT_EVALUATION_MATRIX.md` says it is frozen for `1.0.0`.
- The evaluator equal-shares points within each dimension.
- The named hidden allocations total 43 despite a 45-point dimension.
- The named accessibility allocations total 14 despite a 10-point dimension.
- Public tests are a 15-point all-or-nothing dimension and are counted again in engineering quality.

Do not repair these in the legacy v1 directory. Preserve them as the documented meaning of historical runs and implement corrected semantics in a new versioned suite.
