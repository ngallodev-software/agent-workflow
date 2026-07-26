# Architecture

`agent-workflow` is a local, terminal-first orchestration and evidence system. The repository owns durable execution semantics; prompt packs own project-specific work decomposition; target repositories own implementation source.

The complete visual inventory is in [Repository Chart Pack](diagrams/REPOSITORY_CHART_PACK.md).

## Architectural principles

1. Durable JSON/JSONL records and immutable receipts are authoritative.
2. `status.json`, rendered ledgers, tmux capture, and logs are projections or observations.
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

## Major components

| Area | Modules | Responsibility |
|---|---|---|
| CLI/config | `cli.py`, `config.py`, `doctor.py` | live parser, configuration, local capability checks |
| Sessions/processes | `sessions.py`, `runner.py`, `executors.py`, `tmux.py`, `process.py` | canonical launch, process ownership, structured streams, retry/recovery |
| Durable state | `state.py`, `events.py`, `messages.py`, `ledger.py` | status projections, append-only lifecycle/control records, ledgers |
| Evidence | `receipts.py`, `metrics.py`, `provider_evidence.py`, `lifecycle.py` | final seals, metrics, provider usage, review/accept/reject receipts |
| Workflows | `workflow.py`, `scheduler.py`, `workflow_service.py`, `approval.py`, `bindings.py`, `workflow_receipt.py`, `workflow_templates.py`, `routing.py` | graph validation/replay, scheduling, approvals, result binding, aggregate seals, templates, advice |
| Prompt packs | `pack.py`, `manifests.py`, `native_jobs.py`, `contracts.py` | scaffold, DAG validation, checksums/archive, structured results |
| Evaluation | `evaluation.py`, `eval/*`, `inspect_adapter.py`, `integrations/*` | collectors, scoring, immutable trials, cohort comparison, optional adapters |
| MCP | `mcp/server.py`, `mcp/services.py` | optional bounded read-only stdio adapter over shared read services |
| Tests | `tests/acceptance`, `tests/invariants`, `tests/future`, `tests/live`, `tests/release` | installed-product journeys, compact authority matrices, executable future specifications, live compatibility, and distribution checks |

## Runtime state

The default XDG state root is:

```text
~/.local/state/agent-workflow/
└── runs/
    └── <session-id>/
        ├── status.json                    # mutable projection
        ├── source-baseline.json
        ├── prompt.md
        ├── launch-prompt.md
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
        ├── control-events.jsonl
        ├── assignments.jsonl
        ├── patch.diff
        ├── final-status.json
        ├── final-receipt.json             # canonical read-only run seal
        ├── collections/
        ├── scope/
        ├── scores/
        └── receipts/                      # canonical read-only lifecycle chain
```

A worktree-local `.delegations/<session-id>` symlink points to the durable run directory. Git local exclude metadata hides `.delegations/`, and deleting the worktree does not delete evidence.

## Session execution boundary

The session service resolves agent identity, class, executor, model, permissions, structured/interactivity mode, pane capacity, and no-go authorization. It writes initial contracts, then invokes the generated Python runner through tmux. The runner:

1. records the execution transition;
2. starts the executor as a process group and forwards interrupts;
3. preserves stdout JSONL/text and stderr separately with capture bounds;
4. emits heartbeat/control/evaluation evidence;
5. collects completion, structured result, commands, scope, patch, and metrics;
6. derives provider evidence before sealing;
7. writes `final-status.json`, validates contracts, and under `seal.lock` atomically installs a read-only `final-receipt.json`; verification reads the receipt and sealed artifacts through stable beneath-root descriptors that reject symlinks in every path component.

Retries create a new run ID and preserve `retry_of` lineage. They do not overwrite prior evidence.

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

The current MCP server is optional, local stdio, and read-only except for pack validation. It uses the public pinned `mcp` package and bounded shared read services. It exposes no launch, workflow mutation, lifecycle mutation, raw shell, tmux, arbitrary paths, terminal capture, or HTTP transport.

The current and planned boundary is in [MCP server](MCP_SERVER.md). Future tools must add durable idempotency and call existing services. Streamable HTTP requires a separate authorization ADR.

## Security posture

- schema, ID, type, size, and path validation at every external boundary;
- configured-root containment after resolution and symlink rejection;
- atomic writes and append/fsync-before-projection event ordering;
- canonical receipts are regular, non-symlink, read-only files; sealed authority inputs are reopened only through receipt-matched beneath-root descriptors;
- prompt/source/config/command/artifact SHA-256 provenance;
- no automatic merge, branch deletion, failed-worktree cleanup, remote execution, or autonomous model selection;
- no-go models require explicit recorded authorization;
- external evaluator/oracle material stays outside delegated worktrees;
- logs and terminal capture never grant approval or prove message delivery.

See [Security](../SECURITY.md) and [MCP server](MCP_SERVER.md).

## Testing, release, and packaging

The default test authority is the installed product, not private Python helpers. Acceptance tests build a wheel, install it into an isolated virtual environment, and invoke public executables across real process, Git, and filesystem boundaries. A compact invariant layer covers security, replay, scheduler, provider-accounting, and cohort rules that need exhaustive matrices. Strict future tests describe approved backlog outcomes; live tmux/provider compatibility is opt-in. See [Testing](TESTING.md).

Release assets are checked by `scripts/audit-release-assets.py`; `MANIFEST.sha256` must cover every distributable file. The release gate runs tests, compile checks, shell syntax checks, prompt-pack validation, manifest verification, and deterministic archive tooling checks. Third-party MCP SDK source is not vendored or packaged; only the pinned optional dependency and dependency record remain.

The repository is pre-public-release. License, reporting, supported-host, and release-ownership decisions remain blockers in [Public release readiness](PUBLIC_RELEASE_READINESS.md).

## Hardening roadmap

The current deterministic versus guidance-driven feature inventory is maintained in [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md). The priority/dependency plan is [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md). These documents do not replace `BACKLOG.md`; they explain why the active HARD/REL tasks exist and which authority boundaries they close.

## Planned aggregate orchestrator messaging

The current implementation has durable per-session steer/progress/ack records and explicit reusable-agent lifecycle transitions. It does not yet have a multi-session aggregate orchestrator inbox or deterministic supervisor that resumes an orchestrator when children complete.

The planned design keeps per-session journals and sealed lifecycle evidence authoritative, adds a supervisor-owned append-only aggregate inbox as delivery authority, and uses one shared hashed `tmux wait-for` channel only as a wake hint. Fixed orchestrator notifications contain opaque event IDs rather than child-controlled text. See [Durable two-way messaging](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md) and the collision-safe [`orchestrator-two-way-messaging`](../prompt-packs/orchestrator-two-way-messaging/) pack.
