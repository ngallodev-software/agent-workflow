# Feature module architecture

This document applies DEC-009 to the current repository.

## Module classes

| Class | Current examples | Packaging rule |
|---|---|---|
| Authority kernel | contracts, paths, process facade, lifecycle, receipts, configuration, command catalog | Always installed; no imports from optional feature implementations |
| Built-in feature | direct orchestration, workflow, supervisor, SQLite index, benchmarking, evaluation, future hierarchy and tmux UI | Shipped in the main distribution behind bounded packages and explicit commands/configuration |
| Optional dependency feature | MCP today; visual benchmark and evaluator integrations through existing extras | Code may ship in the wheel, but external SDKs install only through named extras; absence must not break core commands |
| Trusted plugin | future `agent-workflow-spec` and later extracted first-party features | Separate distribution discovered through `agent_workflow.plugins` entry points and explicitly enabled |
| Repository-only tooling | `Jenkinsfile`, Jenkins job template/setup script, GitHub workflows, maintainer release checks | Retained in source control and source archives; excluded from installed modules, executables, and runtime bundles |

## Near-term boundaries

- `agent_workflow.process` remains a compatibility facade. Environment and redaction policy now live under `agent_workflow.runtime`.
- MCP is installed with `agent-workflow[mcp]`; Jenkins host deployment explicitly requests that feature.
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

1. Complete `process.py` policy extraction without changing its public imports.
2. CLI construction and several dispatch domains are now separated: authoritative argparse tree construction lives in `cli_parser.py`, shared renderers live in `cli_output.py`, and `index`, `workflow`, `worktree`, `pack`, `orchestrator`, reusable-agent context/reuse, evaluation, comparative-benchmark, session/lifecycle, and supervisor dispatch live in dedicated `cli_handlers` modules, all behind unchanged public CLI behavior. Continue one command domain at a time while preserving parser-derived catalogs, completions, plugin registration, and installed help.
3. Split session launch, observation, control, and recovery behind a facade.
4. The first SQLite slice is complete: `index_schema.py` owns database identity, migration SQL, and header validation. Continue by separating discovery, reconciliation/indexing, and query/report services behind `index_store` compatibility imports.
5. Split runner stream control, control bridge, completion collection, and sealing.
6. Independently gate the completed PLUG-001 entry-point host, digest-bound package resources, and installed fixture-plugin journey.
7. Extract only one existing feature after the spec plugin proves the boundary.

Each slice requires focused invariants, installed-wheel evidence, release-asset auditing, and documentation drift review.

## Implemented plugin foundation

The 0.7.7 host discovers `agent_workflow.plugins` metadata without importing disabled candidates, loads only configured names, validates the complete descriptor and package-resource set before exposing an immutable registry, registers plugin-owned top-level commands, and records installed-distribution plus digest-bound package-resource provenance in the parser-derived command catalog. `--no-plugins` provides a core-only recovery route. See [Trusted plugin API](PLUGIN_API.md).
