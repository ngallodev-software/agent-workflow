# agent-workflow

`agent-workflow` is a terminal-first control plane for bounded coding-agent work. It launches agents in isolated Git worktrees and tmux sessions, preserves durable evidence, supports restart-safe dependency graphs, and keeps review and acceptance under operator control.

The project is **pre-public-release**. Core behavior is usable, but public distribution is blocked on license selection, external compatibility runs, and release-governance decisions tracked in [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md).

## What it does

- creates and manages ticket worktrees;
- launches named Codex, Claude, or explicit commands through one execution path;
- records prompts, argv, source state, logs, structured provider events, patches, completion handoffs, and immutable receipts;
- supports status, attach, tail, interrupt, terminate, restart, review, acceptance, and rejection;
- stores durable steer, progress, acknowledgement, and watch records;
- schedules restart-safe workflow DAGs with bounded parallelism, approval gates, result bindings, retries, and aggregate receipts;
- validates and archives prompt packs deterministically;
- collects deterministic evaluation evidence and compares matched baseline/candidate cohorts;
- exposes an optional bounded read-only local stdio MCP adapter.

It does **not** merge branches, kill suspected stalls automatically, provide a daemon or web UI, perform remote execution, or choose models autonomously.

## Requirements

- Python 3.11+
- Git
- tmux
- Bash
- GNU tar and zstd for deterministic `.tar.zst` archives
- a supported coding-agent executable, or an explicit command

Core installation includes `jsonschema`. Optional dependency groups cover evaluation, statistics, telemetry, MLflow, shell completion, and MCP.

## Install

From a source checkout:

```bash
./install.sh
export PATH="$HOME/.local/bin:$PATH"
agent-workflow doctor
```

The installer uses an editable local installation, links the shipped skills into supported discovery roots, and creates a starter XDG configuration without replacing unrelated files. See [Installation](docs/INSTALLATION.md) and [`config/agent-workflow.example.toml`](config/agent-workflow.example.toml).

## First run

```bash
agent-workflow worktree create /path/to/repo TICKET-1 HEAD

agent-workflow launch \
  ticket-1 \
  /path/to/worktrees/ticket-1 \
  ./ticket.md \
  --ticket TICKET-1 \
  --executor codex

agent-workflow status ticket-1 --capture 50
agent-workflow attach ticket-1
```

An explicit executor command can be supplied after `--`:

```bash
agent-workflow launch ticket-1 /path/to/worktree ticket.md -- \
  codex exec --sandbox workspace-write --skip-git-repo-check -
```

Review and disposition remain explicit:

```bash
agent-workflow review ticket-1 --actor reviewer --reason "evidence checked"
agent-workflow accept ticket-1 --actor reviewer --reason "criteria met" --revision SHA
```

## Durable control

```bash
agent-workflow steer ticket-1 "Run the focused tests before editing." --actor orchestrator
agent-workflow watch ticket-1 --after 0 --timeout 300
agent-workflow progress ticket-1 "Tests are green." --actor child
agent-workflow ack ticket-1 MESSAGE_ID "Applied." --actor child
```

The append-only message log is authoritative. tmux wakeups are only best-effort hints. A steer remains pending until the child emits correlated acknowledgement evidence; the current detached-executor late-steering gap is tracked in [BACKLOG.md](BACKLOG.md).

## Workflow graphs

```bash
agent-workflow workflow validate ./workflow.json
agent-workflow workflow start ./workflow-run ./workflow.json
agent-workflow workflow status ./workflow-run ./workflow.json
agent-workflow workflow resume ./workflow-run ./workflow.json
agent-workflow workflow seal ./workflow-run ./workflow.json
agent-workflow workflow verify ./workflow-run ./workflow.json
```

Workflow state is reconstructed from an immutable normalized snapshot and append-only event journal. Child sessions use the normal launch service. Approval nodes rely on canonical lifecycle receipts, and result bindings copy bounded JSON Pointer values from sealed predecessor results.

Authorized templates:

```bash
agent-workflow workflow template pipeline ./spec.json --output ./workflow.json
agent-workflow workflow template parallel-review-fan-in ./spec.json --output ./workflow.json
agent-workflow workflow template implementation-independent-review ./spec.json --output ./workflow.json
```

## Prompt packs

```bash
agent-workflow pack scaffold ./my-pack --phases 3
agent-workflow pack validate ./my-pack
agent-workflow pack archive ./my-pack ./my-pack.tar.zst
```

Prompt-pack dependencies form a validated cross-phase DAG. Tickets may declare JSON Schema result contracts whose validated handoffs are sealed with run evidence. See [Prompt packs](docs/PROMPT_PACKS.md).

## Evaluation

```bash
agent-workflow eval validate ./evaluation.json --pack ./prompt-pack
agent-workflow eval score SESSION
agent-workflow eval report SESSION --format markdown
agent-workflow eval compare ./baseline.json ./candidate.json --output ./comparison.json
```

Raw provider streams are bounded and sealed before normalization. Usage evidence distinguishes delta, cumulative, and terminal totals and never mixes provider-billed cost with local estimates. Cohort comparison requires matched task identities and remains descriptive when samples are too small. See [Evidence and evaluation](docs/EVIDENCE_AND_EVALUATION.md).

## Optional MCP server

Install the `mcp` extra and configure `agent-workflow-mcp` as a local stdio server. The current adapter is read-only and bounded to configured roots. It does not expose launch, workflow mutation, review, destructive lifecycle commands, raw shell, arbitrary paths, terminal capture, or HTTP. See [MCP server](docs/MCP_SERVER.md).

## State and trust

Authoritative run evidence is stored below the configured XDG state root, normally:

```text
~/.local/state/agent-workflow/runs/<session-id>/
```

Worktree `.delegations/` entries are discoverability links, not evidence authorities. Status files and terminal captures are projections. Sealed receipts, lifecycle records, workflow snapshots, workflow journals, and verified child evidence determine state transitions. See [Architecture](docs/ARCHITECTURE.md) and [Security](SECURITY.md).

## Development and testing

```bash
python -m pip install -e '.[dev]'
pytest
./scripts/release-check.sh
```

The default suite is acceptance-first: it builds and installs a wheel, invokes public executables as subprocesses, and exercises real Git/filesystem/process journeys. A compact invariant layer protects security, replay, and accounting boundaries. Strict expected-failure future journeys keep approved TDD work visible, and live tmux/provider checks remain opt-in. See [Testing](docs/TESTING.md).

## Documentation

- [Command reference](docs/COMMAND_REFERENCE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Repository diagrams](docs/diagrams/REPOSITORY_CHART_PACK.md)
- [Operations](docs/OPERATIONS.md)
- [Prompt packs](docs/PROMPT_PACKS.md)
- [Evidence and evaluation](docs/EVIDENCE_AND_EVALUATION.md)
- [Testing](docs/TESTING.md)
- [MCP server](docs/MCP_SERVER.md)
- [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md)
- [Backlog](BACKLOG.md)
- [Contributing](CONTRIBUTING.md)
- [Support](SUPPORT.md)

The repository is the source of truth. Completed implementation prompt packs, release-run ledgers, and one-off audit reports are intentionally not retained as parallel documentation; Git history and the changelog preserve that history.
