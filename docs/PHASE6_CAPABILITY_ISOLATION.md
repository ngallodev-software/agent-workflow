# Phase 6 Capability Isolation

Phase 6 implements `CAP-001`: advanced capabilities should impose near-zero cognitive and runtime cost when they are unused. The phase begins with exposure and import isolation. Code/package extraction is allowed only when a clean one-way boundary and a measurable benefit justify it.

## Exposure audit

The Phase 5 cumulative source already satisfies the first exposure-isolation requirement established by the simplification plan:

- normal orchestrator, implementation, and review command profiles do not expose benchmark administration;
- index administration is not in normal role profiles;
- MCP administration is not in normal role profiles;
- plugin maintenance is not in normal role profiles;
- release-evidence internals are not in normal role profiles;
- hierarchy authority is described by the specialized orchestrator skill rather than injected into the primary skill/common role cards.

`eval benchmark-report` remains in the review profile because it is a bounded evaluation/reporting operation, not the comparative-benchmark administration surface. The top-level `benchmark` command remains an explicit maintainer/operator capability.

No additional agent-visible command deletion is required for this slice.

## Baseline measurement

Measurements below compare the Phase 5 cumulative source with the first Phase 6 import-isolation slice. They use `/usr/bin/python3` with only the repository `src` directory added through `PYTHONPATH`, avoiding the development container's unrelated `sitecustomize` imports. These are directional local measurements, not release budgets.

| Operation | Phase 5 cumulative | Phase 6 slice | Change |
| --- | ---: | ---: | ---: |
| import `agent_workflow.cli_parser` | ~45 ms / 142 modules | ~10 ms / 72 modules | ~78% less wall time; 70 fewer modules |
| import `agent_workflow.cli` | ~73 ms / 165 modules | ~42 ms / 134 modules | ~42% less wall time; 31 fewer modules |
| build scoped `delegate` parser | ~36 ms / 144 modules | ~16 ms / 81 modules | ~56% less wall time; 63 fewer modules |

The exact wall time varies by machine and filesystem cache. Loaded-module counts are the more stable signal for this slice.

The common parser path previously imported modules that are not needed to parse a built-in lifecycle command, including:

- `agent_workflow.command_catalog`;
- `agent_workflow.contracts`;
- `agent_workflow.plugins`;
- `agent_workflow.plugin_api`;
- `importlib.metadata` and related plugin-discovery metadata helpers.

## Change made

The lightweight role-profile names now live in `cli_contract`, which is intentionally dependency-free. `cli_parser` no longer imports `command_catalog` just to obtain those names.

Plugin registry/type imports are also lazy:

- built-in commands that do not require plugin discovery receive no plugin registry;
- plugin-aware surfaces still bootstrap the real registry;
- plugin execution imports `PluginExecutionContext` only when a plugin command is actually dispatched;
- parser plugin registration is skipped when no registry is supplied;
- role-scoped `commands` output treats an absent registry as an empty plugin inventory.

This does not change plugin semantics for plugin-aware commands and does not create a second parser or command authority.

## Package/source footprint review

Approximate Python source footprints at this checkpoint are:

| Candidate capability | Approximate source bytes |
| --- | ---: |
| comparative benchmark package | 203 KB |
| index modules | 77 KB |
| hierarchy package | 63 KB |
| MCP package | 27 KB |
| release-evidence module | 23 KB |
| plugin API/registry | 19 KB |
| telemetry integration modules | 3 KB |

Source size alone is not an extraction reason. The current common path no longer imports the benchmark, index, MCP, hierarchy, telemetry, or release-evidence implementations merely to construct a scoped lifecycle parser. The next Phase 6 review should therefore examine optional capability dependency/import boundaries in the plan's candidate order rather than extracting packages for aesthetics.

## Current conclusion

Keep the durable lifecycle, messaging, workflow, evidence, evaluation, review, and worktree authorities in core. Do not split the benchmark/index/hierarchy trees solely because they are large. Continue with measurement-driven review of publication/visual benchmark tooling first, followed by telemetry integrations.

## Slice 2 — publication/visual benchmark isolation

The first candidate extraction review found no justification for a separate benchmark-visual or publication package. Playwright is already an optional `benchmark-visual` dependency, benchmark administration is outside normal role profiles, and ordinary lifecycle parser startup does not import the benchmark package.

There was, however, a measurable boundary leak *inside* the explicit benchmark surface: importing `agent_workflow.benchmarking.service` eagerly imported visual capture, live-review, human-review, and report-publication implementations even for lightweight operations such as validation/authentication/readiness.

The service facade now loads those implementations only in operations that use them:

- visual capture imports `benchmarking.visual` on demand;
- live-review control/status imports `benchmarking.live_review` on demand;
- review operations import `benchmarking.review` on demand;
- report generation imports `benchmarking.reporting` on demand;
- the automated benchmark pipeline loads its publication/visual dependencies when that pipeline actually runs.

A clean-interpreter import measurement using the same `/usr/bin/python3` method as Slice 1 changed `import agent_workflow.benchmarking.service` from roughly **66–110 ms / 222 loaded modules** to roughly **48–51 ms / 183 loaded modules**. More importantly, `benchmarking.visual`, `benchmarking.reporting`, `benchmarking.live_review`, and `benchmarking.review` are no longer loaded by merely importing the service facade.

This is exposure/import isolation rather than package churn. The visual/reporting source remains in the main distribution because:

1. it is an integral optional stage of the comparative benchmark workflow;
2. its heavyweight browser dependency is already optional;
3. no normal lifecycle path imports it;
4. extracting it would introduce packaging/versioning/interface overhead without a demonstrated additional runtime or cognitive-cost reduction.

The publication/visual candidate is therefore **reviewed and retained in-place behind lazy boundaries**. The next candidate review is telemetry integrations.

## Slice 3 — telemetry integrations

The telemetry candidate review found no runtime import problem because the OpenTelemetry and MLflow adapters were not wired into any CLI, lifecycle, evaluation, benchmark, or public-API path. Their third-party imports were already local to adapter functions.

That also meant the repository was carrying unsupported product surface: two dormant adapter modules, two optional dependency groups, four direct-dependency lock entries, installer `all` extras, and installation documentation for integrations that had no actual user-facing activation path.

Phase 6 therefore deletes rather than extracts this capability:

- remove the dormant OpenTelemetry adapter;
- remove the dormant MLflow adapter;
- remove the `otel` and `mlflow` optional dependency groups;
- remove their direct-dependency lock entries;
- remove them from installer `--extras all`;
- stop advertising them as supported optional feature groups.

Durable Agent Run/evaluation/benchmark evidence remains the source of truth. A future telemetry integration should consume stable public evidence/contracts from outside the normal core unless a concrete in-product use case demonstrates otherwise.

This reduces package/dependency and maintenance surface without changing lifecycle authority or common-path behavior. No replacement abstraction is introduced.

