# Feature module architecture

This document applies DEC-009 to the current repository.

## Module classes

| Class | Current examples | Packaging rule |
|---|---|---|
| Authority kernel | contracts, paths, process facade, lifecycle, receipts, configuration, command catalog | Always installed; no imports from optional feature implementations |
| Built-in feature | direct orchestration, workflow, supervisor, SQLite index, benchmarking, evaluation, hierarchy authority, future hierarchy runtime, and tmux UI | Shipped in the main distribution behind bounded packages and explicit commands/configuration |
| Optional dependency feature | MCP today; visual benchmark and evaluator integrations through existing extras | Code may ship in the wheel, but external SDKs install only through named extras; absence must not break core commands |
| Trusted plugin | future `agent-workflow-spec` and later extracted first-party features | Separate distribution discovered through `agent_workflow.plugins` entry points and explicitly enabled |
| Repository-only tooling | `Jenkinsfile`, Jenkins job template/setup script, GitHub workflows, maintainer release checks | Retained in source control and source archives; excluded from installed modules, executables, and runtime bundles |

## Near-term boundaries

- `agent_workflow.process` remains a compatibility facade. Environment and redaction policy now live under `agent_workflow.runtime`.
- MCP is installed with `agent-workflow[mcp]` only on hosts that need it; Jenkins remains repository-core CI/CD and requests optional profiles explicitly when a job covers them.
- Hierarchy is a built-in optional feature and must live in a dedicated package rather than expanding `sessions.py`, `scheduler.py`, or `cli.py` directly.
- Tmux operator UI, host routing, external-terminal attachment, and collaborative specification authoring remain retained capabilities, but each receives a separate feature or plugin boundary.
- The benchmark package is the current reference for a modular built-in subsystem.

## Dependency direction

```text
repository-only CI/release tooling
              |
              v
       installed product tests
              |
              v
trusted plugins -> public plugin API -> authority kernel <- built-in features
                                           ^
                                           |
                              optional SDK adapters/extras
```

The arrow points toward the dependency. Authority-bearing writes remain in shared services; features provide policy, presentation, adapters, or orchestration above those services.

## Decomposition sequence

1. `process.py` remains the stable facade; environment and redaction policy now live in `agent_workflow.runtime`.
2. CLI parser construction, option/bootstrap handling, shared output, and all major command domains now live in dedicated modules behind the unchanged `agent_workflow.cli` facade. Future CLI work should split only when a real domain remains coupled.
3. Session artifact construction and durable operator control/messaging now live in `session_artifacts.py` and `session_control.py`. Launch, observation, restart/recovery, and authority-changing lifecycle coordination remain the next session decomposition candidates.
4. SQLite database identity/migrations, source discovery/stable reads, and bounded query/report construction now live in `index_schema.py`, `index_sources.py`, and `index_queries.py`. Reconciliation/indexing remains behind `index_store` until a behavior-neutral split has focused recovery evidence.
5. Runner stream control, control bridge, completion collection, and sealing remain future behavior-preserving slices.
6. Independently gate the completed PLUG-001 entry-point host, digest-bound package resources, and installed fixture-plugin journey.
7. Extract only one existing feature after the spec plugin proves the boundary.

Each slice requires focused invariants, installed-wheel evidence, release-asset auditing, and documentation drift review.

## Implemented plugin foundation

The 0.7.8 host discovers `agent_workflow.plugins` metadata without importing disabled candidates, loads only configured names, validates the complete descriptor and package-resource set before exposing an immutable registry, registers plugin-owned top-level commands, and records installed-distribution plus digest-bound package-resource provenance in the parser-derived command catalog. `--no-plugins` provides a core-only recovery route. See [Trusted plugin API](PLUGIN_API.md).
