# DEC-009 — Feature modules and distribution surfaces

- **Status:** decided
- **Date:** 2026-08-01
- **Scope:** source layout, installed runtime, optional features, plugins, and repository-only tooling

## Decision

Keep one small authority kernel and modularize higher-level capabilities behind stable feature boundaries rather than deleting them or allowing them to accumulate in shared files.

Four distribution surfaces are distinct:

1. **Authority kernel:** contracts, validation, paths, bounded process execution, lifecycle, receipts, configuration, and shared read services. Always installed.
2. **Built-in features:** first-party packages shipped in the `agent-workflow` distribution and activated only by their command/configuration surface. Direct orchestration remains the default; hierarchy, benchmark, tmux UI, indexing, evaluation, and supervision evolve as bounded packages.
3. **Optional dependency features:** first-party features whose external SDKs are installed through extras. MCP is the first explicit example and uses `agent-workflow[mcp]`.
4. **Repository-only development/release tooling:** Jenkins, GitHub workflows, release scripts, prompt-pack authoring sources, and maintainer checks. These are core to development and release governance but are not installed as Python modules, executables, or runtime bundle assets unless explicitly named by an installer contract.

Third-party and sibling extensions use the versioned trusted plugin API authorized by DEC-004. Entry-point discovery uses Python package metadata. Plugin code is trusted executable code, not a sandbox. The first API uses a small typed atomic registry; a general hook framework is deferred until multiple plugins require ordered 1:N hooks.

## Rules

- Modularization must preserve immutable authority, evidence schemas, public command behavior, and installed-product journeys.
- Feature code must not mutate core registries during import.
- A feature may depend inward on public kernel services; the kernel must not import a feature implementation.
- Optional feature absence must produce a typed actionable diagnostic, not prevent unrelated commands or tests from running.
- Repository-only files must be proven absent from wheels and runtime installer bundles.
- Large-file decomposition is incremental and behavior-preserving; no broad rewrite release.

## Consequences

Capabilities remain available without forcing every installation or code path to carry every dependency. Jenkins remains a first-class core CI/CD concern while staying outside runtime installations. MCP remains supported and packaged, but its SDK becomes an explicit optional extra. Hierarchy can proceed without replacing direct orchestration.
