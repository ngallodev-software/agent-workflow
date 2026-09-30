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
2. Before any codebase-memory-mcp query, run the bundled safety check:

   ```bash
   bash skills/repo-simplification/scripts/ensure-codebase-memory.sh
   ```

   If the configured/native executable is absent or fails its version probe, the check stops and
   prints the explicit GitHub installation command. To opt into installation, run `--install`; it
   shallow-clones the upstream repository into a temporary directory and delegates to its
   maintained checksum-verifying installer. Never download or execute a remote installer
   implicitly during analysis.
3. Use `codebase-memory-mcp` first for definitions, callers, imports, fan-in/out, and impact.
   If its exact-worktree index is absent or stale, create a fresh non-persistent index and compare
   Git porcelain before and after. Use `rg` for literals, docs, manifests, and configuration.
4. If the repository uses OpenSpec, run the bundled pinned-version safety check before querying
   planning state:

   ```bash
   bash skills/repo-simplification/scripts/ensure-openspec.sh
   ```

   The check requires the qualified OpenSpec version used by Agent-Workflow's import boundary.
   If it is absent or different, it stops and prints the explicit pinned npm installation command.
   Installation is opt-in through `--install`; never download or execute a remote installer
   implicitly during analysis.
5. Treat OpenSpec as planning/specification authority when present, not as repository-analysis or
   execution authority. Inspect only the planning material needed for the audit:

   ```bash
   openspec list --specs --json
   openspec show SPEC_ID --type spec --json
   openspec validate --all --strict --json
   ```

   Use Codebase Memory, `rg`, Git, and Agent-Workflow's own evaluation/evidence contracts for
   repository reachability, runtime provenance, executable acceptance, and evaluation intent.
   Do not recreate SpecGen repository-analysis or evaluation-intent objects merely because older
   workflows used them, and do not invent an OpenSpec change when the target repository has none.
6. Triangulate every candidate across four surfaces:
   - source and call graph: reachable callers, entry points, imports, and tests;
   - runtime/configuration: CLI, environment, hooks, paths, databases, and live boundaries;
   - packaging/release: `pyproject.toml`/`package.json`/`Cargo.toml`, manifests, installers,
     source archives, wheels, and CI;
   - documentation/contracts: canonical docs, nested compatibility paths, schemas, and examples.
7. Rank findings as `P0` generated-output hygiene, `P1` authority/contract maintenance, `P2`
   bounded private shrinkage, or `P3` research. For each, record ID, evidence paths/lines,
   smallest safe action, dependencies, risk, validation, and status (`new`, `confirmed`,
   `deferred`, `retained`, or `completed`).
8. Preserve these boundaries unless characterization proves otherwise: security/fail-closed route
   decisions, provenance, receipts and cancellation, public APIs, database authority/migrations,
   package entry points, and standalone compatibility paths.
9. Evaluate before editing. Prefer deletion or a private helper over a new framework. For a
   proposed removal, prove no consumers and clean build/install/package-content behavior. For a
   consolidation, first lock characterization fixtures for null, legacy, malformed, rollback,
   ordering, and failure semantics. Stop at the first changed contract.
10. Validate in layers and report each separately: syntax/compile, focused characterization,
   component suite, installed-product/build/package smoke, release-content audit, and live or
   external acceptance. Never turn a technical pass into a policy, deployment, or live-runtime
   claim.

## Existing prior art to reuse

- `codebase-memory-mcp` and Agent-Workflow's `index` commands: structural search, call tracing,
  change impact, durable evidence projection, and exact-worktree indexing;
- Git porcelain and `git archive`: provenance, dirty-state preservation, and source-release proof;
- `rg`: fast literal/config/document reference search;
- OpenSpec's spec/change inventory, show, and strict validation commands: planning truth when the
  target repository already uses OpenSpec;
- `scripts/ensure-openspec.sh`: a fail-closed exact-version check and explicit, opt-in pinned npm
  installation path for OpenSpec;
- `scripts/ensure-codebase-memory.sh`: a fail-closed executable/configuration check and explicit,
  opt-in GitHub bootstrap through codebase-memory-mcp's maintained installer;
- Agent-Workflow's `eval validate`, `eval score`, `eval report`, `assess-sealed-runs`,
  `scripts/audit-release-assets.py`, `scripts/release-check.sh`,
  package builders, and existing pytest suites: reuse their authority instead of creating a
  second release or test framework.

Do not add a dependency, database, service, generic transaction framework, custom graph crawler,
or broad abstraction for an audit. Existing commands are the deterministic tooling; they identify
proof targets, not automatic deletion targets.

## Completion artifact

When analysis is complete, write the final human-readable report and any machine-readable evidence
to the repository that was analyzed, not only to an external temporary location or the analyst
checkout. Use a neutral,
repository-local directory such as `docs/repo-analysis/` and a dated, collision-free filename like
`REPO_SIMPLIFICATION_<YYYYMMDD>.md`; copy JSON evidence beside it when produced. Do not overwrite
an existing report: add a timestamp or revision suffix. Record the destination paths in the final
report and preserve the target repository's unrelated dirty changes. If the target is read-only or
its documentation policy forbids the copy, report that gap and do not claim artifact completion.

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
