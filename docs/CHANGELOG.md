
# Changelog

## Unreleased

- Complete the evaluation/benchmark templating task by maintainer direction while preserving its environment limitations as release-wide follow-up.
- Implement REL-005 with schema-validated release policy metadata, a synchronized direct-dependency lock, JUnit test evidence, CycloneDX SBOM generation, source/build provenance, optional artifact digests, and enforceable release-blocker status.
- Add the complete durable two-way orchestrator messaging design, authority/failure model, security requirements, acceptance strategy, and four supporting Mermaid diagrams.
- Add collision-free backlog items `MSG-001` through `MSG-007`, assign the previously unowned `BKL-001` and `BKL-002` work, and preserve `HARD-*`, `DEC-001`, and `MCP-003` ownership boundaries.
- Add a six-phase multi-agent `orchestrator-two-way-messaging` prompt pack with parallel foundation, delivery, recovery, and security/acceptance lanes plus an independent gate.
- Add the repository-wide feature determinism and security assessment as a canonical planning reference.
- Add priority-ordered HARD/REL backlog tasks with explicit dependencies, prompt-pack ownership, release blockers, and collision rules.
- Add three detailed multi-agent prompt packs for deterministic enforcement foundations, execution isolation/sensitive content, and public-beta trust/release work.
- Block the existing MCP mutation pack on immutable authority, MCP read-boundary hardening, and authenticated principals without duplicating MCP-003 ownership.
- Add the `release-drift-auditor` skill and deterministic release-audit checks for duplicate task IDs, unknown backlog ownership, cross-pack collisions, undocumented active packs, and stale future-test IDs.
- Align the execution protocol with acceptance-first testing and separate-worktree parallel delegation.

## 0.2.4 — 2026-07-27

- Enforce interactive-first implementation launches with explicit pane-capacity
  fallback to structured non-interactive evidence runs.
- Add the ChatGPT evaluation and benchmark templating handoff.
- Implement installed deterministic templates for evaluation plans, benchmark manifests, sealed assessments, benchmark reports, evidence-ledger rows, and lifecycle archives.
- Add benchmark manifest/report contracts, explicit unavailable-data handling, cohort and case-digest identity checks, unmatched-trial accounting, deterministic renderer commands, and checksum-free archive planning.
- Bind exported trial collections to their sealed run receipt, provider evidence, raw stream, and verified score before declaring assessment completeness.
- Keep generated execution-protocol assets and renamed diagram links in sync.

## 0.2.3 — 2026-07-26

- Integrate the bounded process substrate, artifact/path/schema integrity controls, and MCP read-boundary hardening from the sealed foundation runs.
- Correct Codex/Claude hook configuration separation and add a Codex-specific code-discovery gate.
- Add focused process, path-integrity, MCP-boundary, and hook installation acceptance/invariant coverage.
- Record the foundation-run ledger and sealed-evidence assessment handoff for independent review.
- Add evidence-first exported sealed-run assessment, truthful ledger evaluation states, and strict future journeys for the next hardening and messaging work.
- Correct security documentation that previously overstated symlink containment, preventative sandboxing, authenticated review, and release-integrity guarantees.
- Add hardening dependency and parallel-execution diagrams plus a public-release gate plan.

## 0.2.2 — 2026-07-25

- Replace the 239-test, 46-file implementation-heavy suite with installed-wheel acceptance journeys, compact security/state/accounting matrices, release checks, opt-in live compatibility, and strict expected-failure future specifications.
- Exercise real public CLI journeys for installation surfaces, Git worktrees, external executors, durable messages, retries, structured provider evidence, workflow approvals, sealed result binding, aggregate receipts, interactive-agent reuse, prompt packs, and evaluation comparisons.
- Publish the previously missing `evaluation-runtime` schema after the installed evaluation lifecycle exposed that sealed collection could not validate its own runtime contract.
- Remove private-helper and mock-driven tests that primarily locked parser, dictionary, command-vector, or prose assumptions.
- Add GitHub Actions coverage for Python 3.11 through 3.13 and document the acceptance-first test policy.
- Consolidate operations, prompt-pack, evidence/evaluation, MCP, testing, and public-release guidance into a small canonical documentation set.
- Remove completed prompt packs, ticket-completion ledgers, session checkpoints, changed-file/cleanup artifacts, and historical design reports from the public source surface while preserving history in Git.
- Reduce the MCP follow-on pack to the single active mutation phase and align it with shared-service, idempotency, evidence, and acceptance-test requirements.
- Add contributing, support, public-release-readiness, testing-strategy, and release-path documentation and diagrams.
- Mark license selection, vulnerability reporting, supported-host compatibility, and release ownership as explicit blockers rather than implying public-release readiness.

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
