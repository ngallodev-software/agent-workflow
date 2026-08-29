---
name: repo-simplification
description: Analyze and evaluate repository simplification candidates with deterministic evidence. Use for over-engineering audits, generated-artifact cleanup, duplicate authority or documentation analysis, dead-code/refactor triage, and deciding whether a rewrite, deletion, consolidation, or private helper is safe.
---

# Repository simplification

Produce a bounded, evidence-first simplification audit. Default to `NO_REWRITE` and read-only
work. A candidate is not approved because it looks duplicated: prove ownership, reachability,
packaging/runtime consumption, semantic equivalence, and a reversible validation path.

## Workflow

1. Read the repository steering file and its sole unfinished-work register. Record the exact
   checkout, branch, dirty baseline, and requested scope; preserve unrelated changes.
2. Use `codebase-memory-mcp` first for definitions, callers, imports, fan-in/out, and impact.
   If its exact-worktree index is absent or stale, create a fresh non-persistent index and compare
   Git porcelain before and after. Use `rg` for literals, docs, manifests, and configuration.
3. Before any SpecGen command, run the bundled safety check:

   ```bash
   bash skills/repo-simplification/scripts/ensure-specgen.sh
   ```

   If SpecGen is absent, the check stops and prints the explicit GitHub installation command.
   To opt into installation, run `--install`; it shallow-clones the upstream repository into a
   temporary directory and delegates to SpecGen's own `scripts/install.sh`. Never download or
   execute a remote installer implicitly during analysis.
4. If a canonical specification exists or the work needs durable requirements/evaluation intent,
   use the installed SpecGen application rather than inventing a report parser:

   ```bash
   specgen repo analyze TARGET [--spec SPEC] --mode agent-workflow > repository-analysis.json
   specgen repo drift repository-analysis.json TARGET
   specgen evals intent SPEC
   ```

   These commands are optional; do not invent a spec or assume an Agent-Workflow target.
5. Triangulate every candidate across four surfaces:
   - source and call graph: reachable callers, entry points, imports, and tests;
   - runtime/configuration: CLI, environment, hooks, paths, databases, and live boundaries;
   - packaging/release: `pyproject.toml`/`package.json`/`Cargo.toml`, manifests, installers,
     source archives, wheels, and CI;
   - documentation/contracts: canonical docs, nested compatibility paths, schemas, and examples.
6. Rank findings as `P0` generated-output hygiene, `P1` authority/contract maintenance, `P2`
   bounded private shrinkage, or `P3` research. For each, record ID, evidence paths/lines,
   smallest safe action, dependencies, risk, validation, and status (`new`, `confirmed`,
   `deferred`, `retained`, or `completed`).
7. Preserve these boundaries unless characterization proves otherwise: security/fail-closed route
   decisions, provenance, receipts and cancellation, public APIs, database authority/migrations,
   package entry points, and standalone compatibility paths.
8. Evaluate before editing. Prefer deletion or a private helper over a new framework. For a
   proposed removal, prove no consumers and clean build/install/package-content behavior. For a
   consolidation, first lock characterization fixtures for null, legacy, malformed, rollback,
   ordering, and failure semantics. Stop at the first changed contract.
9. Validate in layers and report each separately: syntax/compile, focused characterization,
   component suite, installed-product/build/package smoke, release-content audit, and live or
   external acceptance. Never turn a technical pass into a policy, deployment, or live-runtime
   claim.

## Existing prior art to reuse

- `codebase-memory-mcp` and Agent-Workflow's `index` commands: structural search, call tracing,
  change impact, durable evidence projection, and exact-worktree indexing;
- Git porcelain and `git archive`: provenance, dirty-state preservation, and source-release proof;
- `rg`: fast literal/config/document reference search;
- SpecGen's `repo analyze`, `repo drift`, `evals intent`, and contract validation: generic
  repository evidence and machine-readable evaluation intent when applicable;
- `scripts/ensure-specgen.sh`: a fail-closed presence/version check and explicit, opt-in GitHub
  bootstrap through SpecGen's maintained installer;
- Agent-Workflow's `eval validate`, `eval score`, `eval report`, `assess-sealed-runs`,
  `scripts/audit-release-assets.py`, `scripts/audit-test-suite.py`, `scripts/release-check.sh`,
  package builders, and existing pytest suites: reuse their authority instead of creating a
  second release or test framework.

Do not add a dependency, database, service, generic transaction framework, custom graph crawler,
or broad abstraction for an audit. Existing commands are the deterministic tooling; they identify
proof targets, not automatic deletion targets.

## Output contract

Return a concise report with:

```yaml
verdict: NO_REWRITE | BOUNDED_CHANGE | BLOCKED
confidence: high | medium | low
baseline: exact branch and dirty-state summary
findings: candidate ledger with evidence and validation
retained_boundaries: contracts not to simplify
validation: command, result, limitation for each layer
gaps: missing proof or external gates
```

For implementation, make one coherent candidate change per commit, rerun the inventory after
structural changes, run `git diff --check`, and preserve a rollback point. Do not commit or push
unless the caller explicitly authorizes it.
