
# Changelog

## Unreleased

No unreleased changes.

## 0.2.1 — 2026-07-24

- Reconcile running workflow nodes from verified child provenance and sealed terminal evidence; count existing running nodes against parallelism and require a durable child footprint before recording `running`.
- Make recoverable retries replay-valid and reopen dependency-failed descendants when a prerequisite retry begins or succeeds.
- Store canonical workflow snapshots and aggregate receipts read-only in the atomic rename, reject writable/symlink substitutions, validate journals before append, lock journal reads, fsync directory entries, and refresh workflow projections after scheduling and status reads.
- Reject duplicate dependency/session identifiers in workflow snapshots.
- Validate trial score sets against content-addressed scorer receipts and the sealed final receipt instead of trusting a mutable verdict file.
- Harden provider evidence against symlinked or changing raw streams, empty/conflicting/non-finite terminal usage, nonmonotonic cumulative totals, incomplete cost metadata, and ambiguous duplicate deltas without provider event identity.
- Reject symlinked lifecycle receipt roots, fsync lifecycle directory entries, serialize final-run seal creation/verification, and read/hash final receipts and artifacts from stable non-symlink descriptors.
- Return final-receipt digests from the same lock-scoped descriptor used for verification; read and hash aggregate workflow receipts from one descriptor under the workflow lock.
- Install content-addressed scorer receipts read-only, reject symlink/writable substitutions, and hash the exact score-set bytes validated for lifecycle review.
- Read authority-bearing sealed JSON through beneath-root no-symlink descriptors and recheck receipt size/hash before lifecycle, approval, scheduling, binding, workflow-receipt, or trial decisions.
- Cover required and optional sealed trees in the read-only pass; reject symlink chmod targets and intermediate symlink components during seal creation and verification.
- Write parent and child workflow input snapshots, native-job source snapshots, and job-binding receipts read-only before their atomic rename and before executor launch.
- Add focused regression coverage and supersede the original 0.2.0 critical-review conclusion.

## 0.2.0 — 2026-07-24

- Add restart-safe workflow graphs with receipt-backed approval gates, bounded
  JSON Pointer result binding, aggregate workflow receipts, deterministic graph
  templates, and explainable routing advice.
- Add bounded sealed provider stream evidence with explicit delta, cumulative,
  and terminal usage semantics; preserve cached, cache-write, reasoning, billed,
  estimated, currency, retry, error, and steering evidence without double counting.
- Extend immutable trial evidence and cohort comparison validity checks.
- Harden final and lifecycle receipt verification against mutable status
  projections, symlinks, writable receipts, substitutions, omissions, and stale
  workflow snapshots.
- Complete the workflow integration gate, update CLI/help/skills/man pages, add
  repository and MCP architecture chart packs, and publish the MCP mutation
  implementation proposal and threat model.
- Remove the unused vendored MCP Python SDK source snapshot; retain only the
  pinned optional dependency and public-API integration.
- Track bounded context and assignment history for interactive agents with
  explicit completion, same-worktree ranking, stale-idle policy, exact-lineage
  automatic reuse, globally unique active names, and configurable pane capacity.
- Validate prompt-pack dependencies as a cross-phase DAG and collect structured,
  schema-validated task results into sealed run evidence.

## 0.1.8

- Add configurable agent names, classes, executor/model allowlists, explicit
  no-go authorization, permission defaults, and interactive/detached routing.
- Make the orchestrator-left, vertically stacked agent-pane layout configurable;
  enable tmux mouse support and named pane borders by default.
- Add the global routing enforcement decision and MCP next-phase research,
  review, planning, and implementation handoff pack.
- Add the `agent-workflow-orchestrator` skill and install all workflow skills into shared, Codex, and Claude discovery roots with ownership-safe idempotent behavior.
- Document the optional local stdio MCP architecture decision without adding runtime MCP code.
- Remove stale one-off validation/implementation artifacts and generated Python bytecode from source distributions; add a cleanup audit.
- Remove host-specific checkout and worktree paths from documentation and tests; use portable placeholders instead.
- Remove an unrelated project-specific adapter, contracts, receipt paths, and tests so the package remains provider- and project-neutral.
- Add versioned evaluation, completion, provenance, command, score, lifecycle, and final-receipt contracts with packaged JSON Schemas.
- Preserve Codex/Claude structured event streams, separate stderr, enforce time/token budgets, capture patches, and seal validated run evidence.
- Add baseline/post scope and command collectors, JUnit regression attribution, deterministic receipt-backed scorers, external oracle boundaries, public fixtures, ledgers, and reports.
- Add explicit review/accept/reject receipts, append-only lifecycle events, multi-signal diagnostics, paired comparison statistics, and stable failure categories.
- Reuse Inspect SWE adapters behind an optional Docker evaluation seam; add optional SWE-bench, OpenTelemetry, MLflow, and shell-completion integrations.
- Correct live Codex non-Git and Claude structured-output command requirements and preserve structured executor settings across retries.

## 0.1.4

- Add sealed execution metrics, control evidence, deterministic regression-eval
  fixtures, and stronger durable message validation.

## 0.1.3

- Refresh the global executable and agent-skill installation release.

## 0.1.2

- Add collector-owned worktree completion handoffs, sealed completion-collection
  receipts, and acceptance enforcement for valid collected completion evidence.
- Repair installed schema discovery and preserve structured explicit Codex/Claude
  executor metadata.

## 0.1.1

- Add required YAML frontmatter to every shipped agent skill.
- Make all YAML templates syntactically valid before placeholder substitution.
- Add comprehensive release-asset auditing for skills, templates, schemas, links, versions, duplicate portable assets, and manifest coverage.
- Add regression tests for skill metadata and parseable template assets.
- Scope release auditing to distributable files and enforce complete manifests.
- Reject prompt traversal and malformed configuration types.
- Preserve terminal run evidence and requested worktree-base provenance.
- Pass durable prompt-pack/session context to Codex and Claude executors.
- Make install/uninstall symlink handling portable and ownership-safe.
- Remove inert source-root, prompt-pack-root, and failed-worktree config knobs.

## 0.1.0

Initial terminal-first workflow release.

### Included

- XDG configuration and persistent run state
- isolated Git worktree creation/removal/listing
- fresh named tmux session per delegation
- prompt and command provenance with SHA-256 hashes
- live logs and structured session status
- attach, tail, capture, interrupt, terminate, kill, and retry controls
- conservative potential-stall observation
- prompt-pack scaffolding and validation
- deterministic tar.zst archives and SHA-256 output
- compatibility shell wrappers
- reusable skills, schemas, templates, examples, and documentation
- natural placement for global `--json` and `--config` options
- dirty-worktree launch guard with an explicit `--allow-dirty` escape hatch
- release validation, security guidance, roadmap, and consolidated release checks

### Intentionally excluded

- automatic merging
- automatic stall termination
- daemon or web UI
- remote execution
- GitHub synchronization
- automatic model selection
- multiple terminal backends
