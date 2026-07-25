# agent-workflow

`agent-workflow` is a terminal-first workflow for delegating bounded implementation tickets to coding agents without losing observability, source provenance, or review discipline.

It provides:

- one isolated Git worktree per ticket;
- one fresh, named `tmux` session per delegation;
- schema-validated, sealed prompts, commands, event streams, provenance, patches, and completion records;
- foreground, tail, inspect, interrupt, terminate, kill, and restart controls;
- durable parent/child progress, steering, acknowledgement, and blocking wait
  records for active runs;
- multi-signal health diagnostics based on terminal, heartbeat, lifecycle, and log state;
- deterministic evaluation collectors, scorers, ledgers, comparisons, and review receipts;
- prompt-pack scaffolding, structural validation, checksums, and deterministic `.tar.zst` archives;
- reusable ticket-completion and phase-gate templates;
- skills for orchestration, prompt-pack construction, delegated implementation, and independent review.

It intentionally does **not** provide automatic merging, automatic agent killing, a daemon, a web UI, remote execution, or autonomous model selection.

## Requirements

- Linux or another POSIX-like environment
- Python 3.11+
- Git
- `tmux`
- Bash
- Python package `jsonschema>=4.18,<5` (installed automatically by `install.sh`)
- GNU `tar` (with `--sort`, `--mtime`, and ownership-normalization options) and
  `zstd` for deterministic `.tar.zst` creation

Task manifests use a constrained YAML shape. PyYAML is used when available; a built-in parser keeps manifest parsing offline-capable. JSON Schema validation uses `jsonschema`.

## Install

From the extracted repository:

```bash
./install.sh
```

The installer installs the checkout in editable mode into the current user's
Python environment, including core dependencies and a pip-managed launcher in
`~/.local/bin`. It also installs workflow skills by symlink and creates a
starter config if one does not exist. Use `--extras eval,stats` for selected
optional dependency groups or `--extras all` for every optional group. Use
`--no-deps` only when the required dependencies are already installed; it uses
a source-link launcher instead.

Make sure `~/.local/bin` is on `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Source checkout

Use any normal Git checkout. The repository is the source of truth; installed command and skill links are not independent copies.

## Planning and backlog

[BACKLOG.md](BACKLOG.md) is the single authoritative register for unfinished,
blocked, and deferred work. Design documents retain detailed rationale and
acceptance material, but link back to the backlog rather than duplicating task
lists.

Global instructions and the installed orchestration skill route suitable work
through this application. Host hooks are only a narrow future guardrail for
recognizable direct delegation commands; see
[global agent routing](docs/GLOBAL_AGENT_ROUTING.md).

## First configuration

Edit the user configuration file. Use a worktree root appropriate for the host:

```toml
[paths]
worktree_root = "<worktree-root>"

[terminal]
backend = "tmux"
stall_minutes = 10
mouse = true
orchestrator_side = "left"
max_interactive_agent_width = 2
max_interactive_agent_vertical = 3

[agents]
preferred_names = ["larry", "moe", "curly"]
generated_prefix = "agent"
default_executor = "codex"
non_interactive_tmux = "dedicated_session"
default_class = "implementation"
reuse_stale_minutes = 120

[agents.profiles.moe]
class = "implementation"
executor = "codex"
model = "gpt-5.6-luna"

[agents.profiles.curly]
class = "implementation"
executor = "claude"
model = "haiku"

[agent_classes.exploratory]
interactive = false
default_executor = "claude"
default_model = "haiku"

[agent_classes.exploratory.models]
claude = ["haiku"]
codex = ["gpt-5.4-mini"]

[agent_classes.review]
interactive = false
default_executor = "codex"
default_model = "gpt-5.4-mini"

[agent_classes.review.models]
claude = ["haiku", "sonnet"]
codex = ["gpt-5.4-mini", "gpt-5.6-luna"]

[agent_classes.implementation]
interactive = true
default_executor = "codex"
default_model = "gpt-5.4-mini"

[agent_classes.implementation.models]
claude = ["haiku", "sonnet"]
codex = ["gpt-5.4-mini", "gpt-5.6-luna", "gpt-5.6-terra"]

[executors.codex]
command = ["codex", "exec", "--sandbox", "workspace-write", "--skip-git-repo-check", "-"]
interactive_command = ["codex"]
models = ["gpt-5.4-mini", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"]
default_model = "gpt-5.4-mini"
no_go_models = ["gpt-5.6-sol", "*fast*"]
permission_args = ["--ask-for-approval", "on-request"]

[executors.claude]
command = ["claude", "--print"]
interactive_command = ["claude"]
models = ["haiku", "sonnet", "opus", "fable"]
default_model = "sonnet"
no_go_models = ["opus", "fable"]
permission_args = ["--permission-mode", "manual"]
```

## Core workflow

```bash
agent-workflow doctor
agent-workflow worktree create /path/to/example P0-01 HEAD
agent-workflow launch   example-p0-01   /path/to/worktrees/example/p0-01   ./phase-0/tickets/P0-01.md   --ticket P0-01   --pack example-phases-0-2   --executor codex
```

Or provide an explicit command:

```bash
agent-workflow launch example-p0-01 /path/to/worktree ticket.md -- \
  codex exec --sandbox workspace-write --skip-git-repo-check -
```

By default, Git worktrees must be clean at launch. Use `--allow-dirty` only for an intentional continuation or recovery; retries automatically preserve and reuse the existing worktree.

Use `--executor codex` or `--executor claude` to select a configured executor.
Use `--agent-name NAME` to request a configured preferred name. Without it, the
orchestrator assigns the first unused preferred name and then generates
`generated_prefix-NN` names after the pool is exhausted. Named profiles bind
an agent name to an executor/model pair; explicit conflicting launch options
are rejected. The assigned name is written to run evidence and shown in the
tmux pane border.
Use `--agent-class exploratory|review|implementation` to select work policy.
Classes define interactivity and allowed executor/model pairs; named profiles
may narrow a class but cannot escape it. The built-in exploratory class is
non-interactive and permits only Claude Haiku or `gpt-5.4-mini`; review is also
non-interactive; implementation is interactive by default. Additional classes
are ordinary `[agent_classes.NAME]` config tables.
Interactive agents share the orchestrator window by default. Non-interactive
agents use detached named tmux sessions when `non_interactive_tmux` is
`"dedicated_session"`, so invisible workers do not consume a visible pane.
Use `--interactive` or `--no-interactive` to override the configured default.
Use `--model MODEL`; configured defaults apply when it is omitted. Models must
be listed for that executor. A `no_go_models` match is rejected unless the run
uses `--allow-no-go-model`, which is recorded in provenance. Executor-specific
`permission_args` are always applied to configured launches: Codex uses
`--ask-for-approval` and sandbox arguments, while Claude uses
`--permission-mode` and may additionally use `--allowedTools` or
`--disallowedTools`.

Add `--structured` to preserve raw Codex JSONL or Claude stream-JSON while rendering normalized operator output. Use `--interactive` instead to run the native executor TUI on the pane PTY; these modes are mutually exclusive. Durable `steer` records are not automatic TUI keystrokes: an interactive child must be prompted to read and acknowledge them, or an operator must send terminal input separately. Retries preserve the saved executor identity, stream format, original prompt source, and pack root.
Installed workflow skills are linked into `~/.agents/skills`, `~/.codex/skills`,
and `~/.claude/skills`. Invoke `$agent-workflow-orchestrator`,
`$prompt-pack-builder`, `$delegated-implementation`, or `$phase-gate-review`
in Codex, or use `/` instead of `$` in Claude. The installer refuses to replace
unrelated paths, so every installed name remains an unambiguous link to this
checkout.

Observe and foreground:

```bash
agent-workflow list
agent-workflow status example-p0-01 --capture 50
agent-workflow attach example-p0-01
agent-workflow tail example-p0-01
```

Interrupt and retry without overwriting evidence:

```bash
agent-workflow interrupt example-p0-01
agent-workflow restart example-p0-01
```

Exchange durable control records without polling status. A steer is a pending
request until the child explicitly acknowledges its message ID; it is not proof
that a one-shot executor has consumed a late prompt. `watch` always replays the
fsynced message log; when tmux is available it uses `tmux wait-for` only as a
best-effort local wakeup hint, so a missed hint cannot lose a control record.

```bash
agent-workflow steer example-p0-01 "Run the focused tests before editing." --actor orchestrator
agent-workflow watch example-p0-01 --after 0 --timeout 300
agent-workflow progress example-p0-01 "Tests are green; reviewing scope." --actor child
agent-workflow ack example-p0-01 MESSAGE_UUID "Applied at checkpoint." --actor child
```

### Reusing an interactive agent

Interactive agents retain bounded durable assignment context, not a raw
transcript. A child must explicitly complete its assignment before reuse:

```bash
agent-workflow agent task-complete SESSION --actor AGENT --summary "Implemented parser" --tag parser --file src/parser.py
agent-workflow agent candidates /path/to/worktree --ticket TICKET --pack PACK
agent-workflow agent reuse SESSION ./next-task.md --actor orchestrator --ticket TICKET --pack PACK
```

Candidates must be idle, live, compatible, unexpired, and in the exact same
worktree. Similar work is ranked for an operator, but automatic reuse is
restricted to exact ticket or retry lineage. Reassignment remains
`reuse_pending` until the child acknowledges the correlated steer message.
Names are globally leased across interactive panes and detached agents, so no
two active runs can use the same configured or generated agent name.

When the interactive pane limit is full, an attached CLI prompts before doing
anything destructive: close enough explicitly idle panes, run the new job as a
detached non-interactive task, or cancel. Automation can choose explicitly with
`--pane-limit-action close-idle|non-interactive|cancel`; non-TTY callers using
the default `prompt` policy fail closed with structured choices.

The default interactive grid creates two agent columns to the right of the
orchestrator before adding vertical splits. It then balances agents across the
two columns, with at most three agents per column (six total).

## Structured task results and dependency graphs

Prompt-pack task dependencies are validated as a cross-phase DAG. Tickets may optionally declare a JSON Schema result contract; validated `result.json` artifacts and collection receipts are copied into and sealed with the durable run. See [Workflow Foundations Plan](docs/WORKFLOW_FOUNDATIONS_PLAN.md).

## Prompt packs

```bash
agent-workflow pack scaffold ./my-project-prompt-pack --phases 3
agent-workflow pack validate ./my-project-prompt-pack
agent-workflow pack archive ./my-project-prompt-pack ./my-project-prompt-pack.tar.zst
```

## Deterministic evaluation

```bash
agent-workflow eval validate ./evals/evaluation.json --pack ./prompt-pack
agent-workflow launch eval-p0-01 /path/to/worktree ticket.md \
  --ticket P0-01 --executor codex --structured \
  --evaluation ./evals/evaluation.json
agent-workflow eval score eval-p0-01
agent-workflow eval report eval-p0-01 --format markdown
agent-workflow ledger ./prompt-pack
agent-workflow review eval-p0-01 --actor reviewer --reason "gates checked"
agent-workflow accept eval-p0-01 --actor reviewer --reason "approved" --revision SHA
```

Baseline commands and scope are captured before the agent; post scope is captured before post commands. Collector artifacts are sealed before scoring. Evaluator-only oracle material remains outside the checkout and is addressed by ID and SHA-256.

Inspect AI, statistics, OpenTelemetry, MLflow, and generated shell completions are optional extras. Their adapters are intentionally experimental seams: the Inspect seam reuses the public `inspect_swe` Codex and Claude agents inside an Inspect-owned Docker sandbox, while paid model trials and external backend/harness validation remain operator-run gates.

## State and evidence

Authoritative records are stored under:

```text
~/.local/state/agent-workflow/runs/<session-id>/
```

Each worktree receives a discoverability symlink at `.delegations/<session-id>`. Deleting a worktree therefore does not delete the authoritative evidence bundle. `final-receipt.json` hashes every required artifact; `events.jsonl` and immutable review receipts record later lifecycle actions without rewriting sealed agent evidence.

## Compatibility scripts

The `scripts/` directory preserves the original helper filenames as thin wrappers around the CLI. Lifecycle behavior belongs only in `src/agent_workflow/`.

## Documentation

- `EXECUTION_PROTOCOL.md`
- `DELEGATION_RUNBOOK.md`
- `docs/PROMPT_PACK_STANDARD.md`
- `docs/ARCHITECTURE.md`
- `docs/MODEL_TIERS.md`
- `docs/TEST_POLICY.md`
- `docs/STALL_RECOVERY.md`
- `docs/MIGRATING_EXISTING_ASSETS.md`
- `CLEANUP_AND_REMOVAL_AUDIT.md`
- `SECURITY.md`

## Development validation

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src
./scripts/release-check.sh
```
