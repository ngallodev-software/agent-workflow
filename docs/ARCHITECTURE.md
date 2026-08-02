# Architecture

`agent-workflow` is a local, terminal-first orchestration and evidence system. The repository owns durable execution semantics; prompt packs own project-specific work decomposition; target repositories own implementation source.

The complete visual inventory is in [Repository Chart Pack](diagrams/REPOSITORY_CHART_PACK.md).

## Architectural principles

1. Durable JSON/JSONL records and immutable receipts are authoritative.
2. `status.json`, rendered ledgers, tmux capture, logs, and SQLite rows are projections or observations.
3. The CLI, workflow scheduler, and MCP adapter use shared services; there is no alternate executor path.
4. Every delegated ticket receives isolated Git source state and a durable run directory.
5. Approval is a separate evidence-backed lifecycle dimension, never implied by process success.
6. Provider usage and cost are normalized only from bounded raw evidence with explicit semantics.
7. Networked/multi-host behavior is deferred until a measured need and explicit authorization exist.

## Ownership model

```text
agent-workflow repository
  execution, tmux, durable state, schemas, workflow policy, receipts, evaluation

prompt pack
  project phases, dependency graph, tickets, references, result contracts, gates

target repository/worktree
  implementation source, project-native tests, legitimate generated artifacts
```

## Plugin-first decomposition

The current distribution remains the execution host. Version 0.7.8 implements the first narrow, versioned trusted-plugin host, including digest-bound schema and asset package resources; independent MOD-GATE-1 review remains open under PLUG-001. The first external first-party plugin should be the sibling `agent-workflow-spec` repository, which owns collaborative specification authoring and deterministic compilation into existing prompt packs and evaluation artifacts. Core continues to own tmux/process/session execution, durable state, receipts, lifecycle authority, workflow safety, and prompt-pack validation required at launch.

This is an additive migration, not an immediate rename or broad repository split. Installed plugins are trusted code, must be explicitly enabled and version-compatible, and may register only bounded command namespaces, schemas, assets, read services, and diagnostics. LangGraph may be an optional spec-authoring adapter, but its checkpoints never replace canonical JSON, append-only events, approval receipts, compiler receipts, or sealed execution evidence. See [Trusted plugin API](PLUGIN_API.md) and [Collaborative specification compiler and plugin-first decomposition](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md).

## Approved bounded hierarchical orchestration

DEC-005 approves an explicitly enabled bounded three-tier hierarchy: a root orchestrator manages multiple team leads, and each team lead eventually supervises worker sessions in panes within its own tmux window. The current `agent_workflow.hierarchy` package implements immutable hierarchy/team-delegation contracts, canonical digests, capability narrowing, read-only contract-set installation, append-only fsynced local journals, idempotent imported-message handling, deterministic replay, and digest-sealed team/root receipts that verify exact declared evidence. The authority phase remains in review at HIER-GATE-0; tmux topology, team runtime, messaging, scheduling, and recovery remain gated. Durable hierarchy records remain authoritative; tmux sessions/windows/panes and optional external terminal windows are projections. The design intentionally reuses canonical session, workflow, inbox, receipt, and worktree services rather than introducing another executor or scheduler path. See [Hierarchical multi-team orchestration design](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md) and [DEC-005](DECISIONS/DEC-005-HIERARCHICAL-ORCHESTRATION.md).

## Implemented bounded supervision and self-healing

The current runtime includes a foregroundable supervisor governed by [DEC-006](DECISIONS/DEC-006-BOUNDED-SELF-HEALING.md). It separates runner heartbeat, executor/process liveness, semantic progress, and known blocked state; records bounded health, terminal, permission, incident, process-result, and remediation evidence; repairs reconstructable mutable status; and may issue one bounded progress probe. Interrupt and orphan restart rules are disabled by default and must be explicitly authorized. The supervisor cannot grant permissions, widen resource or delegation policy, change acceptance criteria, merge work, or delete evidence.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/self-healing-loop-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/self-healing-loop-light.svg">
  <img alt="Bounded self-healing supervisor loop" src="assets/self-healing-loop-light.svg" width="100%">
</picture>

The detailed topology, evidence contracts, state model, security boundary, and remaining dependency plan are in [Self-healing supervisor architecture](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md).

## Rebuildable searchable projection

[DEC-007](DECISIONS/DEC-007-REBUILDABLE-SQLITE-PROJECTION.md) adds a host-local SQLite projection without changing the evidence authority model. A single indexer scans validated run and workflow artifacts, writes normalized searchable fields plus source-file/record provenance in one transaction per run, and exposes curated read-only queries. The supervisor performs an incremental sync after each cycle by default.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/evidence-index-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/evidence-index-light.svg">
  <img alt="Authoritative JSON and JSONL evidence projected into a rebuildable SQLite query store" src="assets/evidence-index-light.svg" width="100%">
</picture>

The database is not lifecycle, permission, acceptance, workflow, or remediation authority. Removing it and running `agent-workflow index rebuild` is a supported recovery operation. Raw prompts, message bodies, terminal bodies, and large logs remain outside SQLite; indexed rows retain bounded normalized fields, source path, sequence, schema identity, and SHA-256 provenance. See [SQLite evidence index architecture](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md).

## Major components

| Area | Modules | Responsibility |
|---|---|---|
| CLI/config | `cli.py`, `cli_parser.py`, `cli_runtime.py`, `cli_output.py`, `cli_handlers/*`, `config.py`, `doctor.py` | compatibility dispatch facade, authoritative live parser construction, shared output rendering, command-domain handlers, configuration, local capability checks |
| Sessions/processes | `sessions.py`, `session_artifacts.py`, `session_control.py`, `runner.py`, `executors.py`, `tmux.py`, `process.py` | canonical launch facade, delegated artifacts, durable operator control, process ownership, structured streams, retry/recovery |
| Health/supervision | `health.py`, `diagnostics.py`, `supervisor.py` | liveness/progress separation, bounded terminal/resource evidence, incident classification, deterministic remediation |
| Durable state | `state.py`, `events.py`, `messages.py`, `ledger.py` | status projections, append-only lifecycle/control records, ledgers |
| Search projection | `index_schema.py`, `index_sources.py`, `index_queries.py`, `index_store.py` | database identity/migrations, stable source discovery, bounded query construction, and deterministic rebuild/incremental reconciliation behind the public facade |
| Evidence | `receipts.py`, `metrics.py`, `provider_evidence.py`, `lifecycle.py` | final seals, metrics, provider usage, review/accept/reject receipts |
| Workflows | `workflow.py`, `scheduler.py`, `workflow_service.py`, `approval.py`, `bindings.py`, `workflow_receipt.py`, `workflow_templates.py`, `routing.py` | graph validation/replay, scheduling, approvals, result binding, aggregate seals, templates, advice |
| Hierarchy authority | `hierarchy/contracts.py`, `hierarchy/journals.py`, `hierarchy/receipts.py` | opt-in fixed-depth contracts, capability narrowing, immutable contract sets, append-only journals, deterministic replay, and digest-sealed team/root receipts; no runtime/tmux authority yet |
| Prompt packs | `pack.py`, `manifests.py`, `native_jobs.py`, `contracts.py`, `path.py` | scaffold, no-follow inventory validation, checksums/archive, structured results |
| Evaluation | `evaluation.py`, `eval/*`, `inspect_adapter.py`, `integrations/*` | collectors, scoring, immutable trials, cohort comparison, optional adapters |
| MCP | `mcp/server.py`, `mcp/services.py` | bounded read-only stdio adapter over shared read services |
| Tests | `tests/acceptance`, `tests/invariants`, `tests/future`, `tests/live`, `tests/release` | installed-product journeys, compact authority matrices, executable future specifications, live compatibility, and distribution checks |

## Runtime state

The default XDG state root contains authoritative run evidence and a separately rebuildable query projection:

```text
~/.local/state/agent-workflow/
├── index/
│   ├── agent-workflow.sqlite3            # disposable/searchable projection
│   └── index.lock                         # exclusive indexer writer lock
└── runs/
    └── <session-id>/
        ├── status.json                    # mutable projection
        ├── source-baseline.json
        ├── prompt.md
        ├── launch-prompt.md
        ├── command-catalog.json            # parser-derived full CLI contract
        ├── command-card.md                  # role-scoped signatures
        ├── launch-contract.json             # immutable v1/v2 launch authority
        ├── command.json
        ├── run-provenance.json
        ├── executor-events.jsonl          # bounded raw stream evidence
        ├── executor-stderr.log
        ├── output.log
        ├── completion.md
        ├── completion.json
        ├── result.json                    # optional structured task result
        ├── provider-evidence.json         # derived and sealed
        ├── execution-metrics.json
        ├── process-result.json             # exact process exit/signal/truncation facts
        ├── run-health-samples.jsonl        # bounded liveness, resource, progress samples
        ├── terminal-events.jsonl           # changed, redacted interactive snapshots
        ├── permission-events.jsonl         # observed waits, denials, and clears
        ├── incident-events.jsonl           # typed unattended-diagnosis findings
        ├── remediation-events.jsonl        # bounded action and verification trail
        ├── control-events.jsonl
        ├── messages.jsonl                 # authoritative session messages
        ├── steering-delivery.jsonl        # adapter delivery/disposition evidence
        ├── assignments.jsonl
        ├── patch.diff
        ├── final-status.json
        ├── final-receipt.json             # canonical read-only run seal
        ├── collections/
        ├── scope/
        ├── scores/
        └── receipts/                      # canonical read-only lifecycle chain
```

A worktree-local `.delegations/<session-id>` symlink points to the durable run directory. Git local exclude metadata hides `.delegations/`, and deleting the worktree does not delete evidence. The SQLite file may be deleted or migrated independently because all indexed state is reconstructable from these source artifacts.

## Session execution boundary

The session service resolves agent identity, class, executor, model, permissions, structured/interactivity mode, pane capacity, and no-go authorization. It writes initial contracts, then invokes the generated Python runner through tmux. The runner:

1. records the execution transition;
2. starts the executor as a process group and forwards interrupts;
3. preserves stdout JSONL/text and stderr separately with capture bounds;
4. emits heartbeat/control/evaluation evidence and services configured cooperative steering delivery;
5. collects and substantively validates completion, structured result, commands, scope, patch, and metrics;
6. derives provider evidence before sealing;
7. writes `final-status.json`, validates contracts, and under `seal.lock` atomically installs a read-only `final-receipt.json`; verification reads the receipt and sealed artifacts through stable beneath-root descriptors that reject symlinks in every path component.

Retries create a new run ID and preserve `retry_of` lineage. They do not overwrite prior evidence.

All repository-owned non-interactive subprocesses use `process.py`. Requests are argv-only, shell-disabled, process-group owned, timeout-bounded, and capped per output stream. A timeout sends `SIGTERM` to the group and escalates to `SIGKILL` after the request grace period. Captured and optional spooled output is redacted before retention, and results record duration, truncation, exit/signal outcome, stable error category, controlled-environment policy, and resolved executable identity. The child environment is rebuilt with a fixed locale and controlled `PATH`; ambient variables are copied only through an executor policy allowlist. Explicit command launches are retained as argv but classified `unclassified`.

The one deliberate terminal boundary is tmux itself: pane creation, observation, wake hints, and attach remain host-terminal operations. They use bounded process calls where capture is possible; `attach-session` uses `os.execvp` to transfer terminal ownership and is not a captured child execution.

## Durable messages and wakeups

Control/progress/acknowledgement records are appended and fsynced. Consumers replay by sequence/cursor. `tmux wait-for` is only a local wakeup accelerator; a missed or coalesced signal cannot lose a record. A steer remains pending until a correlated acknowledgement or executor-specific delivery record proves a stronger state.

## Workflow model

A normalized workflow snapshot is immutable input. `workflow-events.jsonl` is the authoritative append-only state transition and node-binding journal. `workflow-status.json` and `workflow-run.json` are rebuilt projections.

The scheduler:

- replays and validates contiguous event sequence and snapshot digest;
- reconciles running nodes from matching child provenance or sealed terminal evidence;
- requires a durable child footprint before recording `running`;
- propagates dependency failures and reopens only dependency-failed descendants during prerequisite retry;
- enforces bounded parallelism across both existing running nodes and new launches;
- verifies approval nodes from canonical lifecycle receipt chains;
- resolves result bindings only from completed ancestor runs with sealed `result.json` evidence;
- copies bounded values into parent binding snapshots and child `workflow-inputs.json`, both installed read-only before executor launch, and binds their digest into child provenance;
- computes routing advice but delegates actual selection to existing class/executor/model policy;
- launches through the canonical session service;
- records retry lineage and terminal reasons.

Only three graph templates are authorized: pipeline, bounded parallel review with fan-in, and implementation followed by independent review.

A terminal workflow can be sealed into `workflow-receipt.json`, which is atomically installed read-only under `workflow.lock` and commits to the snapshot, event journal, exact node set and states, retry/binding history, child final receipts, completions, input binding digests, approval digests, and terminal disposition. Verification reads, mode-checks, and hashes the receipt from one non-symlink descriptor, rebuilds it from durable evidence under the same workflow lock, and compares exactly.

## Approval authority

Execution state and review disposition are separate. Creating a lifecycle receipt derives completion state, task tier, executor identity, and evaluation requirements from receipt-listed terminal artifacts read through beneath-root descriptors rather than mutable `status.json`; the status file is updated only as a projection after the receipt append. Canonical approval reconstruction requires `receipts/` itself to be a real directory, then scans only contiguous, read-only, regular files through stable descriptors. Receipt creation fsyncs the directory entry. Each receipt must match its filename/action/session and the canonical final-receipt digest. Acceptance additionally checks the exact completion revision, score stability, valid collected completion, task tier, and reviewer independence where required.

## Provider and evaluation evidence

Raw executor events must be stable regular non-symlink files, are capped at 16 MiB for parsing, and are fully hashed from one file descriptor. Provider adapters classify only known boundaries as `delta`, `cumulative`, or `terminal`. Terminal totals are not added to deltas; conflicting or empty terminal updates, nonmonotonic cumulative totals, non-finite values, malformed/truncated streams, mixed nonterminal modes, incomplete cost metadata, and unidentified duplicate deltas are incomplete. Cached and reasoning tokens remain details.

`provider-evidence.json` is sealed with the run. Trial extraction verifies the final seal and uses the digest of the exact receipt bytes verified under `seal.lock`, checks complete provider evidence, and validates the score set against regular read-only content-addressed scorer receipts bound to the same final receipt. Lifecycle review hashes the exact score-set bytes it validated. Provider-billed and locally estimated cost remain separate; currency and price-catalog compatibility determine whether cost comparisons are valid.

## MCP boundary

The current MCP server is local stdio and read-only except for pack validation. It uses the public pinned `mcp` package and bounded shared read services. Configured repository/state roots and pack paths are checked component-by-component without following links; unsafe entries fail closed. It exposes no launch, workflow mutation, lifecycle mutation, raw shell, tmux, arbitrary paths, terminal capture, or HTTP transport.

The current and planned boundary is in [MCP server](MCP_SERVER.md). The read-only adapter reuses the parser-derived command catalog and verified launch-contract reader for capability discovery and per-run command context; it does not generate executable MCP tools from CLI commands. Future mutation tools must add durable idempotency, call existing services, and preserve launch-contract v2 command artifacts for MCP-launched children. Streamable HTTP requires a separate authorization ADR.

## Security posture

- schema, ID, type, size, and path validation at every external boundary;
- component-wise no-follow traversal and configured-root containment for pack, native-job, prompt, and MCP paths;
- packaged schemas are the sole runtime contract authority; duplicate IDs, malformed assets, and missing assets fail closed. Source-checkout lookup is selected only when the executing package is the checkout; migration lookup is not runtime schema resolution;
- atomic writes and append/fsync-before-projection event ordering;
- canonical receipts are regular, non-symlink, read-only files; sealed authority inputs are reopened only through receipt-matched beneath-root descriptors;
- prompt/source/config/command/artifact SHA-256 provenance;
- no automatic merge, branch deletion, failed-worktree cleanup, remote execution, or autonomous model selection;
- no-go models require explicit recorded authorization;
- external evaluator/oracle material stays outside delegated worktrees;
- logs and terminal capture never grant approval or prove message delivery.

See [Security](SECURITY.md) and [MCP server](MCP_SERVER.md).

## Testing, release, and packaging

The default test authority is the installed product, not private Python helpers. Acceptance tests build a wheel, install it into an isolated virtual environment, and invoke public executables across real process, Git, and filesystem boundaries. A compact invariant layer covers security, replay, scheduler, provider-accounting, and cohort rules that need exhaustive matrices. Strict future tests describe approved backlog outcomes; live tmux/provider compatibility is opt-in. See [Testing](TESTING.md).

Release assets are checked by `scripts/audit-release-assets.py`; no mutable `MANIFEST.sha256` is required in the source tree. Prompt-pack transfer checksums are opt-in, while deterministic archives carry their own canonical `MANIFEST.json`. The release gate runs tests, compile checks, shell syntax checks, prompt-pack validation, and deterministic archive tooling checks. Third-party MCP SDK source is not vendored or packaged; only the pinned dependency and dependency record remain.

The repository is pre-public-release. License, reporting, supported-host, and release-ownership decisions remain blockers in [Public release readiness](PUBLIC_RELEASE_READINESS.md).

## Hardening roadmap

The current deterministic versus guidance-driven feature inventory is maintained in [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md). The priority/dependency plan is [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md). These documents do not replace `BACKLOG.md`; they explain why the active HARD/REL tasks exist and which authority boundaries they close.

## Planned aggregate orchestrator messaging

The current implementation has durable per-session steer/progress/ack records, explicit reusable-agent lifecycle transitions, the `MSG-001` multi-session aggregate orchestrator registry/inbox, and a foreground `orchestrator watch` supervisor. It uses one hashed shared wake channel only as a hint; fair replay from child journals and per-child cursors remain authoritative.

The implementation keeps per-session journals and sealed lifecycle evidence authoritative; the registry binds verified child sessions and the append-only aggregate inbox is delivery authority only. Future work uses one shared hashed `tmux wait-for` channel only as a wake hint and fixed orchestrator notifications containing opaque event IDs rather than child-controlled text. See [Durable two-way messaging](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md) and the collision-safe [`orchestrator-two-way-messaging`](../prompt-packs/orchestrator-two-way-messaging/) pack.
