# Installation

## Recommended location

Use a normal Git repository as the source of truth:

```text
~/src/agent-workflow
```

Any normal Git checkout is valid. Examples use placeholders rather than host-specific directory names.

Do not use `~/.local/bin` or agent skill directories as the source of truth.

## Install

```bash
cd ~/src/agent-workflow
./install.sh
```

This installs the package and its core Python dependencies in editable user
mode, then wires the launcher, skills, man pages, schemas, evaluation assets,
and active prompt packs. To install optional integrations, use
`./install.sh --extras eval,stats` or `./install.sh --extras all`. The
optional local MCP server uses the pinned stable Python SDK:

The installer does not require an activated virtual environment. It uses the
selected `python3` interpreter, bootstraps pip with `ensurepip` when available,
and otherwise reports the exact interpreter that needs pip. To select another
host Python, use `./install.sh --python /path/to/python3`.

```bash
./install.sh --extras mcp
agent-workflow-mcp --help
```

When the `mcp` extra is requested, the installer also registers the local
stdio server as `agent-workflow` in the user-level Codex and Claude Code
configuration. Existing entries with that name are preserved. The `all`
extra includes `mcp`.

The first MCP release is stdio-only. It exposes bounded run resources and
prompt-pack validation; it does not expose shell execution, raw tmux control,
destructive lifecycle tools, or HTTP transport.

## Installed locations

```text
~/.local/bin/agent-workflow
~/.config/agent-workflow/config.toml
~/.local/share/agent-workflow/schemas/
~/.local/share/agent-workflow/evals/
~/.local/share/agent-workflow/prompt-packs/
~/.local/share/man/man1/
~/.local/state/agent-workflow/runs/
~/.agents/skills/
~/.codex/skills/
~/.claude/skills/
```

The installer links the same repo-owned skill directories into the shared root
`~/.agents/skills`, the Codex root `~/.codex/skills`, and the Claude root
`~/.claude/skills`: `agent-workflow-orchestrator`, `delegated-implementation`,
`prompt-pack-builder`, `phase-gate-review`, and `release-drift-auditor`. Each
name must resolve to the same source directory; the installer refuses unrelated
files or symlinks rather than creating ambiguous divergent copies. See
[`DELEGATION_RUNBOOK.md`](references/DELEGATION_RUNBOOK.md) for invocation names and paired executor launch examples.

XDG environment variables override config, state, and data roots.

Configuration is schema-versioned (`schema_version = 1`) and unknown policy keys
are rejected. The example config includes `[security].mode = "local"`; use
`governed` or `release` for fail-closed ownership and compatibility checks.
Configuration is read without following symlinks. Keep config, state, allowlist,
and policy files user-owned and free of group/world write bits.

## Jenkins host deployment

Jenkins runs builds and tests in an isolated venv. The final pipeline stage
builds a wheel, then calls this installer in wheel mode against the host account named by
`AGENT_WORKFLOW_HOST_INSTALL_USER`, using `AGENT_WORKFLOW_HOST_PYTHON` (default
`/usr/bin/python3`) rather than the build venv. If Jenkins runs as a different
account, configure narrowly scoped passwordless sudo for this deployment or
run the job under the target host account. The pipeline fails if the target is
not configured; it never silently installs only into Jenkins's private home.
The pipeline requests the lightweight `mcp` extra; use `--extras eval` only
when the host is intentionally dedicated to the optional evaluator stack.
