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
- skills for prompt-pack construction, delegated implementation, and independent review.

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

## Recommended source location

```text
/lump/apps/agent-workflow
```

or:

```text
~/src/agent-workflow
```

The repository is the source of truth. `~/.local/bin` and agent skill directories contain installed links, not independent copies.

## Planning and backlog

[BACKLOG.md](BACKLOG.md) is the single authoritative register for unfinished,
blocked, and deferred work. Design documents retain detailed rationale and
acceptance material, but link back to the backlog rather than duplicating task
lists.

## First configuration

Edit `~/.config/agent-workflow/config.toml`. A machine with projects under `/lump/apps` might use:

```toml
[paths]
worktree_root = "/lump/worktrees"

[terminal]
backend = "tmux"
stall_minutes = 10

[executors.codex]
command = ["codex", "exec", "--sandbox", "workspace-write", "--skip-git-repo-check", "-"]

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
agent-workflow launch example-p0-01 /path/to/worktree ticket.md -- \
  codex exec --sandbox workspace-write --skip-git-repo-check -
```

By default, Git worktrees must be clean at launch. Use `--allow-dirty` only for an intentional continuation or recovery; retries automatically preserve and reuse the existing worktree.

Use `--executor codex` or `--executor claude` to select a configured executor.
Add `--structured` to preserve raw Codex JSONL or Claude stream-JSON while rendering normalized operator output. Retries preserve the saved executor identity, stream format, original prompt source, and pack root.
Installed workflow skills are invoked as `$prompt-pack-builder`,
`$delegated-implementation`, and `$phase-gate-review` in Codex, or with `/`
instead of `$` in Claude.

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
- `VALIDATION.md`
- `SECURITY.md`

## Development validation

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src
./scripts/release-check.sh
```
