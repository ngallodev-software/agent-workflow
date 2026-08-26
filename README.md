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

The core intentionally does not own workspace, pane, window, or interactive terminal layout. External interactive hosts are future integrations rather than core dependencies.

## What agent-workflow owns

- Git worktree isolation, source baselines, and provenance;
- Agent Run contracts and worker policy;
- restart-safe workflow DAGs and hierarchical delegation authority;
- persist-first steering, progress, acknowledgement, replay, and correlation;
- controlled process execution and bounded supervision;
- completion handoffs, sealed evidence, receipts, review, and acceptance;
- evaluation plans, scoring, comparative benchmarks, and usage/cost evidence;
- rebuildable SQLite projections and read-only MCP access;
- prompt-pack validation and trusted semantic plugins.

## Agent Run lifecycle

Prepare a headless run:

```bash
agent-workflow agent-run prepare RUN-001 /path/to/worktree prompt.md \
  --executor codex --agent-class implementation --tier medium
```

Start it:

```bash
agent-workflow agent-run start RUN-001
```

Observe and communicate durably:

```bash
agent-workflow agent-run status RUN-001
agent-workflow agent-run progress RUN-001 "implemented parser changes" --actor worker
agent-workflow agent-run steer RUN-001 "also run the integration tests" --actor parent
agent-workflow agent-run ack RUN-001 MESSAGE_ID "applied" --actor worker
```

Review and disposition remain separate from worker completion:

```bash
agent-workflow agent-run review RUN-001 --actor reviewer --reason "evidence inspected"
agent-workflow agent-run accept RUN-001 --actor maintainer --reason "accepted" --revision HEAD_SHA
```

## External worker preparation

An external runtime can consume a prepared Agent Run without being a dependency of the core:

```bash
agent-workflow agent-run prepare RUN-EXT /path/to/worktree prompt.md \
  --worker-mode external --interactive --executor codex
```

Preparation records the durable authority and launch plan but does not launch a process.

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
- [Installation](docs/INSTALLATION.md)
- [Operations and recovery](docs/OPERATIONS.md)
- [Testing strategy](docs/TESTING.md)
- [Prompt packs](docs/PROMPT_PACKS.md)
- [Comparative benchmarks](docs/BENCHMARKS.md)
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

This source tree is the breaking `0.8.0` headless-core rewrite. Older terminal-host-era runtime and schema compatibility is intentionally not carried forward.

## Repository-only CI assets

Jenkins CI and local server-job files remain in the source repository for maintainers. They are repository infrastructure, not installed runtime features; see [Contributing](docs/CONTRIBUTING.md#jenkins-and-repository-only-ci-assets).
