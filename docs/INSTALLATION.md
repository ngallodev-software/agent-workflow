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
mode, then wires the launcher and skills. To install optional integrations,
use `./install.sh --extras eval,stats` or `./install.sh --extras all`. The
optional local MCP server uses the pinned stable Python SDK:

```bash
./install.sh --extras mcp
agent-workflow-mcp --help
```

The first MCP release is stdio-only. It exposes bounded run resources and
prompt-pack validation; it does not expose shell execution, raw tmux control,
destructive lifecycle tools, or HTTP transport.

## Installed locations

```text
~/.local/bin/agent-workflow
~/.config/agent-workflow/config.toml
~/.local/state/agent-workflow/runs/
~/.agents/skills/
~/.codex/skills/
~/.claude/skills/
```

The installer links the same repo-owned skill directories into the shared root
`~/.agents/skills`, the Codex root `~/.codex/skills`, and the Claude root
`~/.claude/skills`. Each name must resolve to the same source directory; the
installer refuses unrelated files or symlinks rather than creating ambiguous
divergent copies. See `DELEGATION_RUNBOOK.md` for invocation names and
paired executor launch examples.

XDG environment variables override config, state, and data roots.
