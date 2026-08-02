# Modularization and decision implementation — 2026-08-01

## Outcome

This pass converts the 0.7.6 backlog/architecture review into an implemented 0.7.7 boundary. No planned capability was deleted. Capabilities that should not burden the authority kernel are retained as built-in features, optional dependency profiles, trusted plugins, or repository-only development/release tooling.

## Decisions now encoded

| Area | Decision | Product consequence |
|---|---|---|
| License | Apache-2.0 | Root license, package metadata, release policy, and distribution inventory agree. |
| Vulnerability reporting | GitHub Private Vulnerability Reporting is the primary channel | Policy is written; repository-admin enablement and a notification drill remain external evidence. |
| Jenkins | Core repository CI/CD, not an installed runtime feature | `Jenkinsfile` and local job setup remain maintained in source and are rejected from wheels/runtime bundles. |
| MCP | Supported first-party optional dependency feature | Base CLI does not require the MCP SDK; `agent-workflow[mcp]` or `--extras mcp` installs/registers it explicitly. |
| Hierarchy | Approved bounded built-in feature | Direct orchestration remains default; hierarchy must live under a dedicated feature package and require explicit activation. |
| Plugins | Approved trusted in-process extension boundary | Separate distributions use `agent_workflow.plugins`; presence grants no authority and disabled candidates are not imported. |
| Module growth | Incremental facade-preserving decomposition | Large modules are split in behavior-neutral slices with installed-product evidence, not through a broad rewrite. |
| Retained optional capabilities | Modularize rather than cut | Host routing, richer tmux UI, external-terminal attachment, and spec authoring keep separate feature/plugin ownership. |

## Implemented source changes

### Stable authority/runtime boundary

- Added `agent_workflow.runtime.environment` for deterministic environment construction.
- Added `agent_workflow.runtime.redaction` for secret detection and evidence redaction.
- Preserved `agent_workflow.process` as the compatibility facade.
- Replaced the hand-written MiniYAML subset with declared `yaml.safe_load` use and adversarial tests.

### Trusted plugin host foundation

Added stable public and host modules:

- `agent_workflow.plugin_api`
- `agent_workflow.plugins`

The 0.7.7 host now provides:

- metadata-only discovery through `agent_workflow.plugins` entry points;
- explicit `[plugins].enabled` activation;
- global `--no-plugins` core-only recovery;
- strict missing, ambiguous, incompatible, malformed, and collision failure;
- a versioned descriptor and bounded execution context;
- atomic registration after the complete enabled set validates;
- plugin-owned top-level command groups;
- `agent-workflow plugins list` inventory;
- installed distribution and entry-point provenance in parser-derived command catalogs;
- plugin commands in orchestrator command cards and sealed launch command artifacts;
- a separately built/installed fixture-plugin wheel acceptance journey.

PLUG-001 remains `in-progress`, rather than being overstated as complete, because declared schema and asset bundle identifiers still require bounded `importlib.resources` resolution/validation before activation and independent MOD-GATE-1 review.

### Distribution boundaries

- Base dependencies now contain only core dependencies; MCP is pinned in the named optional extra.
- Source installation registers MCP clients only when the MCP profile is requested.
- `--no-deps --extras mcp` fails before client edits if the exact supported SDK is absent.
- Wheels and runtime bundles have executable checks rejecting Jenkins and GitHub workflow assets.
- Jenkins remains covered by repository development/release documentation and backlog ownership.

### Correctness fixes found during implementation

- Corrected `worktree create` dispatch referencing a benchmark-only argument.
- Corrected stale hierarchy, release, security, prompt-pack, and backlog lifecycle wording.
- Removed the stale future specification for accepted HARD-004.

## Prompt-pack steering

### `feature-modularization`

The new pack owns MAINT-001, PLUG-001, and ARC-004. Phase 1 now explicitly starts from the implemented 0.7.7 plugin host and permits only the remaining bounded package-resource work; it forbids a competing registry or a general hook framework. ARC-004 remains blocked until a real first-party sibling plugin proves the boundary.

### `hierarchical-multi-team-orchestration`

All hierarchy prompts now require dedicated feature-package ownership, stable core seams, direct orchestration as the default, and no expansion of shared session/CLI modules merely to add hierarchy.

### Public release and installers

Release prompts now distinguish:

- base install from optional profiles;
- repository-core Jenkins assets from runtime-distributed files;
- selected-but-not-yet-enabled vulnerability reporting from completed evidence;
- implemented installer mechanics from real tagged clean-host release proof.

## What remains intentionally modular

| Capability | Boundary | Next trigger |
|---|---|---|
| Hierarchical orchestration | Built-in explicit feature | Execute HIER-001/002 under the dedicated package after the current gates. |
| Collaborative spec authoring | Sibling trusted plugin | Close/gate PLUG-001, then bootstrap `agent-workflow-spec`. |
| Host routing | Optional built-in feature | Implement only after measured direct-routing failures. |
| Rich tmux sidebar/dashboard | Built-in presentation feature | Implement only after popup/current UI evidence shows a real operator gap. |
| External terminal attachment | Optional adapter feature | Keep outside the authority path; add only for demonstrated operator need. |
| MCP mutation | Optional MCP feature | Remains blocked behind authenticated principal/authority work. |
| One extracted existing subsystem | Separate distribution/plugin | Evaluate only after the spec plugin provides operational evidence. |

## Recommended execution order

1. Complete HARD-003, HARD-006, and HARD-007 in parallel; these unblock supervisor, privacy, and authenticated mutation work.
2. Finish PLUG-001 package-resource resolution and run MOD-GATE-1.
3. Continue MAINT-001 with one behavior-neutral CLI parser/dispatch slice, followed by session launch/observation separation.
4. Begin HIER-001 and HIER-002 inside the dedicated hierarchy feature package while security lanes proceed.
5. Enable GitHub Private Vulnerability Reporting and execute the notification drill; then close REL-002.
6. Implement transitive dependency/reproducibility/signing work under HARD-010 and REL-003/004.
7. Bootstrap the sibling spec plugin; only after real use should ARC-004 select one existing subsystem for extraction.

## Validation summary

- release asset audit: passed;
- version synchronization: passed at 0.7.7;
- prompt-pack validation: 17 packs passed;
- shell syntax and Python compilation: passed;
- invariants and future specifications: 152 passed, 11 intentional expected failures;
- release/distribution suite: 10 passed;
- installed fixture-plugin journey: 1 passed;
- installed CLI journeys: 9 passed;
- installed process-boundary journey: 1 passed;
- synthetic paired comparative benchmark journey: 1 passed;
- optional MCP acceptance: not executed because the optional pinned SDK is absent in the review host.

The broad interactive/delegation acceptance collection remains susceptible to host tmux/process readiness stalls in this environment, so this pass does not claim a clean full-suite result. The focused installed-product journeys touching every changed boundary pass independently.
