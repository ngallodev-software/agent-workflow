# agent-workflow

`agent-workflow` is a headless workflow, evidence, evaluation, and delegation engine for coding-agent work.

The durable execution object is an **Agent Run**. A task may produce one or more Agent Runs over its lifetime; each Agent Run has an immutable execution contract, a worker plan, durable messaging, evidence, and a review/acceptance lifecycle.

## Core model

```text
Workflow
  └── Task
       └── Agent Run
            └── Worker
```

A worker has one of two modes:

- **headless** — agent-workflow launches and owns the local worker process group;
- **external** — agent-workflow prepares the Agent Run and execution contract, while another runtime launches the worker.

The core intentionally does not own workspace, pane, window, or interactive terminal layout. External hosts may consume the implemented host-neutral, generation-checked binding/delivery contract in [EXTERNAL_WORKER_BINDING.md](docs/EXTERNAL_WORKER_BINDING.md), while interactive layout remains outside the core.

## What agent-workflow owns

- Git worktree isolation, source baselines, and provenance;
- Agent Run contracts and worker policy;
- restart-safe workflow DAGs and hierarchical delegation authority;
- persist-first steering, progress, acknowledgement, replay, and correlation;
- controlled process execution and bounded supervision;
- completion handoffs, sealed evidence, receipts, review, and acceptance;
- evaluation plans, scoring, review/acceptance evidence, and optional plugin-provided comparative benchmarks;
- rebuildable SQLite projections and read-only MCP access;
- prompt-pack validation and trusted semantic plugins.

## Agent Run lifecycle

For the normal path, create/select the worktree and launch the Agent Run in one deterministic composition:

```bash
agent-workflow delegate RUN-001 prompt.md --repo /path/to/repo \
  --ticket TICKET-001 --base-ref HEAD --role implementation --tier medium
```

`--pack` accepts either the stable `pack_id` or the path to the pack root containing `pack.yaml`. `--job` accepts either a native JSON job path or a task ID declared in `pack.yaml` (for example `P0-00` in a v1 Markdown prompt pack). When `--job` supplies the ticket identity, `delegate` does not invent a conflicting ticket ID from the Agent Run ID.

Dirty worktrees remain fail-closed by default. If pre-existing changes are intentionally part of reconciliation work, pass `--allow-dirty`; Agent-Workflow records that dirty launch baseline rather than silently discarding or normalizing it.

When `--allow-dirty` is used, that approval is also injected into the immutable worker launch context: pre-existing overlapping changes are treated as baseline drift rather than an automatic blocker. Workers must still preserve unrelated drift and stay within the assigned scope. For read-only review/evidence work, the flag records the baseline only; it is not permission to rewrite the pre-existing changes.

`--agent-name` is a logical worker identity, not a model selector. `[agents].preferred_names` controls automatic allocation order only, so an explicit valid name may be outside that list. Normal launches use `--role`, which selects a configured private runtime binding. If an operator intentionally pins executor/model/reasoning for qualification or diagnosis, omit `--role` and use the matching `--agent-class` with the explicit runtime options.

Lineage retries are prepare-first:

```bash
agent-workflow agent-run restart RUN-001 --context-file corrective.md
agent-workflow agent-run start RUN-001-retry1
```

`--context-file` is bound into the retry launch prompt without changing the original ticket prompt. Add `--start` only when immediate execution is explicitly desired.

Independent review prerequisites use sealed completion evidence rather than
requiring acceptance first: a verified, sealed, successfully completed run can
be reviewed before host acceptance, while implementation-to-implementation
dependencies still require acceptance. Explicitly rejected prerequisites remain
blocked.

For Codex linked worktrees, Agent-Workflow grants the worker both the linked
worktree Git administrative directory and the repository's shared Git common
directory so normal commits can write the shared object database and refs.

The lower-level `worktree create`, `agent-run prepare`, and `agent-run start` commands remain available for recovery, diagnostics, and explicit operator control. `delegate` uses those same authorities and produces the same durable Agent Run evidence; it does not introduce a parallel lifecycle.

Observe and communicate durably:

```bash
agent-workflow agent-run status RUN-001
agent-workflow agent-run status RUN-001 --json
agent-workflow agent-run progress RUN-001 "implemented parser changes" --actor worker
agent-workflow agent-run steer RUN-001 "also run the integration tests" --actor parent
agent-workflow agent-run ack RUN-001 MESSAGE_ID "applied" --actor worker
```

The compact `delegate` response includes a `steering` capability block. `agent-run status` exposes the same decision as `steering_supported`, `steering_adapter`, and `steering_reason`. Steering is persist-first: `delivery_outcome=unsupported` means the request is durably recorded but no evidence-capable adapter delivered it to the running worker. Do not treat delivery or persistence as application; correlated acknowledgement is still required.

Review and disposition remain separate from worker completion:

```bash
agent-workflow agent-run review RUN-001 --actor reviewer --reason "evidence inspected"
agent-workflow agent-run accept RUN-001 --actor maintainer --reason "accepted"
```

### Deterministic worker protocol

Implementation and review workers do not author Agent-Workflow protocol JSON.
They record bounded semantic intent through parser-constrained operations:

```bash
agent-workflow agent criterion RUN-001 criterion-id pass --evidence "test receipt"
agent-workflow agent criterion RUN-001 metadata-receipt pass --evidence-file GITHUB_PROMOTION_RECEIPT.md
agent-workflow agent limitation RUN-001 live-fetch --evidence "controlled DNS unavailable"
agent-workflow agent verify RUN-001 -- npm test
agent-workflow agent complete RUN-001 --result completed
```

Agent-Workflow derives identity, Git revisions, changed files, observed command
exit status, schema-valid completion JSON, and acceptance revision. When a
prompt-pack task or native job declares a machine-readable `criteria` catalog,
that catalog is frozen into the Agent Run contract: `agent criterion` rejects
unknown IDs and `agent complete` rejects omitted declared criteria. Newly
scaffolded v1 packs include criterion IDs by default. A `limitation` is always
`not_verified` and is non-gating; it records a controlled environment constraint
separately from source correctness.

Normal runner completion and recovery finalization use the same terminal
pipeline: collect completion/task evidence, collect post-run scope/commands,
write provider evidence, evaluate policy, derive terminal status, update
provenance, write final status, seal, and refresh the projection. An exit code 0
can no longer be interpreted differently by recovery than by the normal runner
when completion evidence is missing or invalid.

New run handoffs are stored under the Agent-Workflow run-state directory rather
than inside the source checkout, preventing runtime evidence from entering
Docker/build contexts. Existing worktree-local handoffs remain readable for
compatibility.

When `--config` is omitted, `agent-run prepare` and `delegate` auto-discover an
exact-root `.agent-workflow-execution.toml`. This repository-local file may
override execution identity (`agents`, `agent_classes`, `executors`, `roles`,
`runtime_aliases`) but cannot override host security, state paths, plugins, or
other administrative policy.

Canonical review/accept/reject operations and prerequisite requirements are
closed, deterministic operation/policy sets. Acceptance derives the revision
from sealed completion evidence; `--revision` is now only an optional
compatibility assertion.

## External worker preparation

An external runtime can consume a prepared Agent Run without being a dependency of the core:

```bash
agent-workflow delegate RUN-EXT prompt.md --workdir /path/to/worktree \
  --worker-mode external --interactive --role implementation
```

The facade records the durable authority and launch plan but does not launch a process.

## Workflows

```bash
agent-workflow workflow validate workflow.json
agent-workflow workflow start ./workflow-run workflow.json
agent-workflow workflow status ./workflow-run workflow.json
agent-workflow workflow resume ./workflow-run workflow.json
agent-workflow workflow seal ./workflow-run workflow.json
```

Workflow eligibility and durable state belong to agent-workflow. Presentation of workers does not.

## Testing

The repository is acceptance-first. Invariant tests protect durable contracts and security boundaries; installed end-to-end journeys exercise public CLI behavior. The core must operate on a machine with no interactive runtime host installed.

```bash
python -m pytest -q tests/invariants
python -m pytest -q tests/acceptance
python -m pytest -q
```

See [docs/TESTING.md](docs/TESTING.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [0.9 skill-first simplification plan](docs/SKILL_FIRST_SIMPLIFICATION_PLAN.md)
- [Installation](docs/INSTALLATION.md)
- [Operations and recovery](docs/OPERATIONS.md)
- [Testing strategy](docs/TESTING.md)
- [Prompt packs](docs/PROMPT_PACKS.md)
- [Benchmark plugin migration](BENCHMARK_PLUGIN_MIGRATION.md)
- [MCP server](docs/MCP_SERVER.md)
- [Plugin API](docs/PLUGIN_API.md)
- [Backlog](docs/BACKLOG.md)
- [Legacy notes](docs/LEGACY_NOTES.md)
- [Contributing, versioning, and CI](docs/CONTRIBUTING.md)

Generate the exact installed command surface directly from the parser:

```bash
agent-workflow commands --format markdown
```

## Future interactive-host integration

The core is deliberately host-independent. A future plugin may project Agent Runs into an interactive coding-agent environment, provide live delivery after durable persistence, and reconcile host bindings, but it must consume public Agent-Workflow contracts rather than become workflow authority. See the [external host/plugin boundary](docs/ARCHITECTURE.md#external-host-and-plugin-boundary) and [backlog](docs/BACKLOG.md).

## Version

Version `0.11.3` builds with installed contract-schema authority so the active environment's packaged schemas cannot be shadowed by a stale user-data copy, while preserving user-site installs outside `sys.prefix`. It retains the 0.11.1 prompt-pack operational fixes for logical agent names, runtime override guidance, steering capability/reporting, copy-safe verification, and host-independent launch-context measurement. The deterministic worker/admin protocol and shared terminal pipeline remain unchanged authority boundaries. See `ARCHITECTURE_SIMPLIFICATION_PLAN.md` for the migration boundary.

## Repository-only CI assets

Jenkins CI and local server-job files remain in the source repository for maintainers. They are repository infrastructure, not installed runtime features; see [Contributing](docs/CONTRIBUTING.md#jenkins-and-repository-only-ci-assets).

## Phase 2 simplification notes

Normal `agent-workflow delegate` output is intentionally compact: run ID, logical role, worker mode, worktree, state, idempotency/worktree indicators, steering capability, and next actions. Use `agent-workflow agent-run status RUN` or `agent-workflow agent context RUN` when detailed durable state is actually needed rather than paying that context cost on every delegation.

## Decision modes

Agent-Workflow has built-in `deterministic`, `typesafe`, and `comparative` decision modes. The TypeSafe-backed modes require the optional `typesafe` install extra and remain bounded to registered semantic seams; deterministic lifecycle/recovery authority does not move to the provider. Unrelated trusted plugins may still advertise additional decision providers or modes through the public plugin API. Inspect the effective capabilities with:

```bash
agent-workflow decision modes
agent-workflow decision providers
agent-workflow decision check
```

Select a mode/profile in configuration or for one invocation with `--decision-mode` / `--decision-profile`. Built-in TypeSafe modes are unavailable when the optional SDK extra is absent; plugin-contributed modes are unavailable unless their plugin is installed and enabled. `--no-plugins` suppresses optional plugins but does not remove built-in deterministic recovery authority.

Modes that advertise comparative capture also require the neutral shared library:

```bash
pip install 'agent-workflow[comparative-eval]'
```

Agent-Workflow persists the already-computed control/candidate pair in the workflow coordinator's `comparative-eval.sqlite` without issuing a second semantic-provider call. Inspect persisted cohorts with `agent-workflow decision report PATH`.

See `DECISION_MODES.md` and `TYPESAFE_ARCHITECTURE_ALIGNMENT.md` for the policy boundary and receipt semantics.

### Live CLI discovery

CLI commands contributed by **enabled** plugins are attached to the live argparse tree dynamically. As a result, top-level help, the parser-derived command catalog, and shell completion reflect the plugins enabled in the selected configuration:

```bash
agent-workflow --help
agent-workflow commands --format markdown
agent-workflow completion bash
```

Use `agent-workflow --no-plugins --help` for the core-only recovery surface. The parser-derived command catalog is the command-reference source of truth; Agent-Workflow does not maintain a separate static Unix man page that could drift from enabled plugin capabilities.

## Optional benchmark capability

The historical comparative benchmark subsystem is no longer part of Agent-Workflow core. Install and enable the separate `agent-workflow-benchmark` plugin to restore the top-level `agent-workflow benchmark ...` command. Core still owns generic sealed-run evaluation, review, acceptance, and lifecycle authority.

## Optional bounded semantic decisions

Agent-Workflow includes an optional built-in TypeSafe provider for the three registered routing judgments. Install `agent-workflow[typesafe]`, provide `TYPESAFE_API_KEY` through the runtime environment, and select `decision_policy.mode = "typesafe"` or `"comparative"`. The provider uses the official SDK `Choice`, `Noul`, and `Score` primitives; deterministic control, fallback, lifecycle, review, and acceptance remain Agent-Workflow-owned. See `DECISION_MODES.md` and `TYPESAFE_ARCHITECTURE_ALIGNMENT.md`.
