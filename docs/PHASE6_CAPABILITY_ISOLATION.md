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

## Slice 4 — MCP isolation review

The MCP candidate does not justify extraction or further runtime restructuring in 0.9.

The current MCP implementation already has the intended optional boundary:

- `agent-workflow-mcp` is a separate explicit stdio entry point;
- the MCP SDK is pinned in the optional `mcp` dependency group rather than core dependencies;
- normal `agent_workflow.cli` import does not load `agent_workflow.mcp`, `agent_workflow.mcp.server`, or the MCP SDK;
- scoped `delegate` parser construction likewise loads none of the MCP package/SDK;
- `mcp.server` imports the third-party `FastMCP` implementation only while constructing the explicit MCP server;
- MCP commands/resources are absent from normal logical-role command profiles;
- the adapter remains read-only and calls existing durable read/application authorities rather than defining another lifecycle.

A clean `/usr/bin/python3` measurement of scoped `delegate` parser construction at this slice was roughly **3–6 ms / 87 modules**, with no MCP package or SDK modules loaded. Normal `agent_workflow.cli` import was roughly **32–38 ms / 134 modules**, also with no MCP modules loaded.

`MCP-003` mutation is explicitly blocked on authenticated principal/idempotency policy and therefore is not an implemented capability available for Phase 6 extraction. It should be reviewed for isolation only if/when that functionality lands.

The read-only stdio adapter is therefore **reviewed and retained in-place behind its existing optional package/install boundary**. No wrapper or separate package is introduced.

### Overlay delivery rule

Beginning with this checkpoint, cumulative changes-only overlays are self-applying and deletion-aware. The archive contains:

- `files/` — cumulative added/modified files relative to the authoritative verified Phase 3 source;
- `OVERLAY-DELETIONS.txt` — cumulative explicit deletions;
- `apply-overlay.sh` — validates the Agent-Workflow repository context, rejects unsafe manifest/source paths and symlink traversal, removes only declared deletion paths, then copies cumulative changed files.

Plain tar extraction is no longer considered sufficient application semantics once deletions exist.

## Slice 5 — hook installation canonicalization

A migration audit found that repeated installation was idempotent only for clean current configurations. Historical duplicate Codex managed blocks, duplicate Claude hook groups, and retired Agent-Workflow-owned hook files could survive indefinitely.

The installer/configurator now treats Agent-Workflow-owned hook state as a canonical projection:

- every historical Codex managed block is collapsed to one current block;
- Claude commands installed from the Agent-Workflow hook directory are removed across duplicate groups before one canonical set is added;
- an externally located codebase-memory gate explicitly supplied by the installer is likewise canonicalized;
- the installed Agent-Workflow hook directory removes retired files only from the bounded set of names owned by Agent-Workflow while preserving unrelated user files;
- repeated installation therefore converges instead of accumulating historical hook state.

One release-level regression journey covers duplicate migration, repeated installation, stale owned-file removal, and preservation of unrelated hooks/files. This is intentionally one broad journey rather than several narrow invariants.

## Slice 6 — evaluation/analytics optional boundaries

The remaining optional evaluation/analytics review covered Inspect/Inspect-SWE, SWE-bench export, and SciPy-backed comparison statistics.

The third-party dependency boundaries were already mostly correct:

- `inspect-ai` and `inspect-swe` are imported only by `inspect_adapter._load_inspect_api()` when the explicit `eval inspect` path executes;
- SciPy is imported only inside comparison functions that require non-default statistical confidence/paired-bootstrap behavior;
- the SWE-bench prediction writer has no third-party dependency;
- normal `agent_workflow.cli` import loads none of the Inspect, SWE-bench, or SciPy surfaces.

One small eager internal coupling remained: importing the general eval command handler also imported the lightweight Inspect adapter and SWE-bench writer even for unrelated eval commands. Those imports are now local to `eval inspect` and `eval swebench-prediction` respectively.

Using a clean `/usr/bin/python3` process with only a minimal PyYAML stub needed to load the eval handler in the measurement environment, eval-handler import changed from **172 loaded modules** to **169 loaded modules** and no longer loads `agent_workflow.inspect_adapter` or `agent_workflow.integrations.swebench`. Wall time remained in the same roughly **40–47 ms** range, confirming this is boundary cleanup rather than a meaningful startup optimization.

No package extraction is justified:

- Inspect dependencies are already optional under the `eval` extra and loaded only on explicit use;
- SciPy is already optional under `stats` and loaded only on explicit statistical paths;
- SWE-bench export is a small deterministic formatter over durable run evidence;
- none of these capabilities increase the normal role-scoped command surface or common lifecycle import path.

## Phase 6 conclusion

`CAP-001` is complete. The phase produced the following simplification outcomes without moving durable authorities into optional packages:

1. common scoped parser/plugin discovery imports were removed from unused lifecycle paths;
2. comparative-benchmark publication/visual/review implementations are lazy behind explicit benchmark operations;
3. dormant OpenTelemetry/MLflow product/dependency surface was deleted rather than wrapped;
4. read-only stdio MCP was confirmed already isolated behind its optional entry point/dependency boundary;
5. hook installation now converges to canonical managed state instead of retaining duplicate/stale historical entries;
6. Inspect/SWE-bench/statistics optional paths are isolated to explicit evaluation operations.

No additional package split has a demonstrated runtime, cognitive, or maintenance benefit at this point. Future capabilities should continue to satisfy the same placement rule as they are introduced rather than keeping Phase 6 open indefinitely.

