# Changelog
- Consolidate the test suite around installed-product journeys and explicit invariant authority: remove private CLI/decomposition tests, reduce the invariant layer from 320 to 247 collected cases and the complete default collection from 411 to 340, add `tests/test-authority.json`, and enforce layer/function/collection/subprocess/wheel-build/runtime drift ceilings in release checks.

- Add immutable repository-closeout receipts with explicit offline/fetch/push
  modes, classified dirty paths, verified post-push remote revisions,
  integration ancestry, completion-sidecar binding, and separate ledger fields.


## 0.7.9 live-run reliability fixes

- Preserve valid terminal attempts as first-class evidence even when executor, completion, budget-policy, evaluation, or acceptance gates are non-green.
- Emit post-seal ledger rows for every terminal run and deterministic score/report artifacts whenever evaluation was planned.
- Require a valid native completion collection as an explicit `completion_presence` scorer.
- Upgrade the rebuildable SQLite index to schema version 2 with separate executor, completion, policy, score, classification, and acceptance-eligibility fields.
- Add append-only evidence repair with exact sealed-source binding, deterministic structural-only completion normalization, immutable repair receipts, evaluation/ledger linkage, and SQLite schema version 3 repair projections.
- Make optional codebase-memory discovery non-persistent by default; require external cache or explicit disposable-tree authorization for persistence, and record bounded ownership/size/digest/cleanup evidence for local tooling artifacts.

## Unreleased

## 0.7.9 — 2026-08-02

- Make a validated interactive `agent task-complete` terminal by default: emit the durable completion, close the otherwise-idle executor, seal the final receipt, and retire the tmux pane. Preserve same-worktree reuse only through explicit `--keep-alive`, and distinguish completion-authorized shutdown from operator cancellation in process evidence.
- Derive CLI and doctor version output from the package version so installed release reporting cannot remain stale after a patch bump.

- Add an exhaustive comparative-benchmark task/evaluation/scoring explanation and expand the primary man page with the same operational interpretation.
- Add a 0.7.8-rebased comparative-benchmark scoring-correction backlog and prompt pack with exact built-in feature, suite mirror, schema, test, release-audit, and plugin-boundary ownership.
- Preserve the current v1 evaluator as historical authority while documenting the spec/matrix version conflict, point-allocation drift, browser coverage gaps, public-test duplicate credit, and the required new-major-version correction strategy.

## 0.7.8 — 2026-08-01

- Completed digest-bound installed plugin schema/asset activation with traversal, collision, missing-file, tamper, and atomic-registration protections plus an installed fixture-plugin journey.
- Implemented the HIER-001/HIER-002 authority layer: fixed-depth immutable contracts, capability and budget narrowing, append-only journals, idempotent imports, deterministic replay, and digest-sealed team/root receipts. Runtime topology remains separately gated.
- Synchronized version, README, installation, help/man, skills, prompt-pack steering, architecture, testing, restore, and release documentation; added regression checks for optional MCP and repository-only Jenkins boundaries.
- Extracted core command-catalog, plugin inventory, doctor, shell-completion, and configuration dispatch from the monolithic CLI dispatcher without changing output behavior.
- Extracted sealed-run assessment and evaluation-ledger reporting dispatch from the monolithic CLI facade while preserving JSON, Markdown, file-output, and row-count behavior.
- Isolated CLI global-option normalization, explicit launch-command parsing, version-safe configuration bootstrap, and plugin loading/suppression in `cli_runtime.py`.
- Isolated SQLite projection source discovery, no-follow stable artifact reads, artifact inventory, and source fingerprinting in `index_sources.py` while preserving `index_store` compatibility imports.
- Isolated bounded parameterized SQLite query construction and freshness-bound query report shaping in `index_queries.py` while preserving the `index_store` public facade.
- Isolated delegated-session filesystem artifact construction in `session_artifacts.py`: Git excludes, completion handoffs, durable state links, generated runner scripts, and prompt-pack discovery/identity.
- Isolated durable operator steer/progress/ack messaging, replay/wait cursors, child lifecycle denial, and interrupt/terminate/kill controls in `session_control.py` while preserving the `sessions` facade.
- Extracted one-shot and loop supervisor dispatch into `agent_workflow.cli_handlers.supervisor`, preserving remediation policy construction, session filtering, and loop report schemas.
- Extracted session launch, observation, archival, operator messaging/control, restart, lifecycle review, acceptance, and force-accept dispatch into `agent_workflow.cli_handlers.session`, preserving pane-cap fallback and durable authority semantics.
- Extracted the complete `benchmark` command domain into `agent_workflow.cli_handlers.benchmark`, preserving comparative-benchmark validation, readiness, runtime attestation/sealing, suite export, planning, execution, review, reporting, verification, and explicit cleanup behavior.
- Extracted the complete `eval` command domain into `agent_workflow.cli_handlers.eval`, preserving validation, templating, scoring, reporting, trial comparison, Inspect, and SWE-bench behavior while keeping direct report rendering explicit.
- Extracted the complete `agent` reusable-context command domain into `agent_workflow.cli_handlers.agent`, preserving durable assignment, completion, candidate-ranking, and reassignment semantics.
- Extracted the complete `orchestrator` registry/inbox/watch command domain into `agent_workflow.cli_handlers.orchestrator`, preserving durable messaging services, bounds, and output schemas.
- Extracted the complete `pack` command domain into `agent_workflow.cli_handlers.pack`, preserving scaffold/checksum/archive behavior plus validation rendering and exit status.
- Extracted the complete `worktree` command domain into `agent_workflow.cli_handlers.worktree`, preserving create/list/remove arguments, structured results, parser behavior, and installed Git worktree journeys.
- Extracted the complete `workflow` command domain into `agent_workflow.cli_handlers.workflow`, preserving template rendering, scheduler/service construction, parser behavior, JSON output, and installed workflow journeys.
- Extracted shared terminal renderers into `agent_workflow.cli_output` and the complete `index` command domain into `agent_workflow.cli_handlers.index`, preserving public parser/catalog behavior, exact index schemas, JSON/table output, and installed CLI journeys.
- Extracted SQLite application identity, schema version, migration SQL, and database-header validation into `agent_workflow.index_schema` while preserving `index_store` imports, exact migration records, rebuild behavior, and installed index journeys.
- Extracted authoritative argparse command-tree construction from the monolithic CLI dispatcher into `agent_workflow.cli_parser` while preserving the `agent_workflow.cli.build_parser` facade, parser-derived catalogs/completions, plugin registration, help, and installed CLI behavior.
- Completed the HIER-002 durable-authority slice with strict team/root receipt schemas, read-only digest sealing, declared journal and evidence verification, required output/review/approval enforcement, budget accounting, later-append/tamper invalidation, and installed-wheel coverage.

## 0.7.7 — 2026-08-01

- Adopt Apache-2.0 and select GitHub Private Vulnerability Reporting as the primary disclosure channel, pending repository enablement proof.
- Define a small authority kernel with built-in feature, optional-extra, trusted-plugin, and repository-only tooling boundaries; approve bounded hierarchy as an explicitly enabled feature.
- Keep Jenkins as core repository CI/CD while excluding its pipeline/job assets from installed wheels and runtime bundles.
- Make MCP an explicit optional install extra and register MCP clients only for requested MCP profiles.
- Replace the hand-written MiniYAML subset with declared safe PyYAML loading and adversarial coverage.
- Start behavior-preserving decomposition by extracting process environment and redaction policy behind the stable `agent_workflow.process` facade.
- Add the feature-modularization prompt pack for module decomposition, the trusted entry-point plugin host, and evidence-gated subsystem extraction.
- Implement the trusted plugin-host foundation with import-free entry-point discovery, explicit enablement, strict version/collision validation, atomic command registration, installed provenance, `plugins list`, `--no-plugins`, and a separately built fixture-plugin wheel journey.
- Correct the worktree-create CLI dispatch regression that referenced benchmark-only assistance-cohort arguments.
- Reconcile canonical backlog states with the 0.7.6 implementation, move completed task IDs to history, promote satisfied prerequisites, close duplicate REL-007 ownership, and add behavior-preserving maintenance follow-up.
- Remove obsolete blocker inventories and the stale HARD-004 future placeholder; update public-release readiness and hierarchy wording to match current decisions.
- Add the 2026-08-01 backlog, architecture, scope, module-decomposition, and library-reuse review.

## 0.7.6 — 2026-08-01

- Decide and implement the comparative benchmark operating policy with subscription-backed Codex and Claude CLI sessions as the default authentication path and API keys/access tokens as optional explicit adapters.
- Add development, internal, and publication policy profiles with sealed repetitions, cache treatment, assistance cohorts, fresh-pair infrastructure retries, interruption handling, paired-bootstrap confidence intervals, effect thresholds, regression limits, and reviewer requirements.
- Add authentication and readiness preflight, truthful provider-billed/API-equivalent/subscription-allocation cost semantics, real-executor stdin prompt delivery, retry-attempt retention, publication browser/font runtime attestation and content-addressed sealing, and operator guidance.
- Harden subprocess stdin/stdout/stderr ownership with selector-based bounded I/O and deterministic descendant cleanup.

## 0.7.5 — 2026-08-01

- Implement the adopted `priority-picker-v1` paired comparative benchmark under the modular `agent_workflow.benchmarking` boundary: packaged suite export, frozen three-phase fixture, coordinator and arm worktrees, synchronized paired execution, timing/token/cache/cost evidence, deterministic 100-point scoring, blinded visual review, 70/30 composite reporting, digest-verified consolidation, verification, and safe cleanup.
- Add versioned run, arm, pair, phase-event, machine-score, human-review, consolidation, executor, and report contracts plus a full synthetic development acceptance journey.
- Adopt `DEC-008`: compare the same canonical task through paired `control_raw/v1` and `workflow_full/v1` worktrees and freeze the initial requirement-to-evaluation matrix under BKL-011.
- Keep actual real-provider cohort and publication-image acceptance under BKL-004 and BKL-010 rather than manufacturing external evidence.

## 0.7.0

- Add explicit local force acceptance with an exact acknowledgement, immutable linked override receipt, and a lifecycle state distinct from ordinary acceptance.
- Enforce Luna-only automatic Codex model selection with bounded low/medium/high reasoning effort and immutable launch evidence.

## 0.5.1

- Add opt-in cooperative late steering with immutable inbox requests, durable delivery/disposition records, correlated acknowledgements, replay/race safeguards, unsupported/expired evidence, and an installed-wheel journey.
- Reject placeholder completion handoffs and require matching identity plus substantive revision, criterion, command, or unresolved evidence.
- Make source cleanliness use a fresh exact-root Git status command while preserving operator global excludes and recording bounded provenance.
- Separate heartbeat, output-log, executor-event, and semantic-progress evidence when diagnosing a stalled run.
- Add recoverable accepted-run archive/clear operations and read-only completion templates.

## 0.5.0

- Adopt `DEC-007` and add a host-local, fully rebuildable SQLite evidence projection while preserving JSON/JSONL, immutable snapshots, and sealed receipts as authority.
- Add `index status|sync|rebuild|verify|query`, versioned migrations, locking, source provenance, corrupt-run quarantine, freshness envelopes, and curated read-only views.
- Adopt `DEC-006` and add bounded foreground self-healing supervision with health, terminal, permission, incident, remediation, and process-result evidence plus safe projection repair and bounded probes.
- Add architecture, operations, security, testing, diagrams, prompt packs, and backlog sequencing for the supervisor and SQLite projection programs.

## 0.3.0 — 2026-07-30

- Add the sandbox-safe child control bridge, exact launcher binding, and an installed-product child-completion journey.
- Make source preflight honor configured Git excludes and make wheel builds discard stale build artifacts.
- Add enforceable, maintainer-selected semantic-version bumping.

## 0.2.5 — 2026-07-27

- Add the delegation-communication-reliability prompt pack with parallel process-hardening tasks for authoritative preflight, durable control handshakes, silent-run recovery, substantive completion validation, and operator enforcement.
- Register the new process tasks in the canonical backlog and add a bounded release-drift audit and transfer archive.
- Add the plugin-first decomposition and sibling `agent-workflow-spec` design while retaining this distribution as the execution host.
- Add the MSG-001 registry/fan-in foundation, parser-derived command catalog, role-scoped launch cards, launch-contract v2 bindings, and bounded read-only MCP command-context resources.
- Complete evaluation/benchmark templating and REL-005 structured release evidence.
- Add the durable two-way messaging design, collision-free MSG ownership, multi-phase prompt pack, determinism/security assessment, hardening packs, drift-auditor skill, and acceptance-first execution protocol.

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
