# agent-workflow

`agent-workflow` is a terminal-first workflow for delegating bounded implementation tickets to coding agents without losing observability, source provenance, or review discipline.

It provides:

- one isolated Git worktree per ticket;
- one fresh, named `tmux` session per delegation;
- persistent prompts, commands, logs, source baselines, and status records;
- foreground, tail, inspect, interrupt, terminate, kill, and restart controls;
- conservative potential-stall detection based on terminal state and log inactivity;
- prompt-pack scaffolding, structural validation, checksums, and deterministic `.tar.zst` archives;
- reusable ticket-completion and phase-gate templates;
- skills for prompt-pack construction, delegated implementation, and independent review.

It intentionally does **not** provide automatic merging, automatic agent killing, a daemon, a web UI, remote execution, or autonomous model selection.

## Requirements

- Linux or another POSIX-like environment
- Python 3.11+
- Git
- `tmux`
- Bash
- `tar` and `zstd` for `.tar.zst` creation

Task manifests use a constrained YAML shape. PyYAML is used when available; a built-in parser keeps installation dependency-free and offline-capable.

## Install

From the extracted repository:

```bash
./install.sh
```

The installer links the permanent source checkout into `~/.local/bin`, installs workflow skills by symlink, and creates a starter config if one does not exist. It performs no network access and creates no virtual environment.

Make sure `~/.local/bin` is on `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Recommended source location

```text
/lump/apps/agent-workflow
```

or:

```text
~/src/agent-workflow
```

The repository is the source of truth. `~/.local/bin` and agent skill directories contain installed links, not independent copies.

## First configuration

Edit `~/.config/agent-workflow/config.toml`. A machine with projects under `/lump/apps` might use:

```toml
[paths]
source_root = "/lump/apps"
worktree_root = "/lump/worktrees"
prompt_pack_root = "~/prompt-packs"

[terminal]
backend = "tmux"
stall_minutes = 10

[executors.codex]
command = ["codex", "exec", "--full-auto", "-"]

[executors.claude]
command = ["claude", "--print"]
```

## Core workflow

```bash
agent-workflow doctor
agent-workflow worktree create /lump/apps/example P0-01 HEAD
agent-workflow launch   example-p0-01   /lump/worktrees/example/p0-01   ./phase-0/tickets/P0-01.md   --ticket P0-01   --pack example-phases-0-2   --executor codex
```

Or provide an explicit command:

```bash
agent-workflow launch example-p0-01 /path/to/worktree ticket.md --   codex exec --full-auto -
```

By default, Git worktrees must be clean at launch. Use `--allow-dirty` only for an intentional continuation or recovery; retries automatically preserve and reuse the existing worktree.

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

## Prompt packs

```bash
agent-workflow pack scaffold ./my-project-prompt-pack --phases 3
agent-workflow pack validate ./my-project-prompt-pack
agent-workflow pack archive ./my-project-prompt-pack ./my-project-prompt-pack.tar.zst
```

## State and evidence

Authoritative records are stored under:

```text
~/.local/state/agent-workflow/runs/<session-id>/
```

Each worktree receives a discoverability symlink at `.delegations/<session-id>`. Deleting a worktree therefore does not delete the authoritative prompt, command, log, or status record.

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
- `VALIDATION.md`
- `SECURITY.md`
- `docs/ROADMAP.md`

## Development validation

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src
./scripts/release-check.sh
```
