# Installation

## Recommended location

Use a normal Git repository as the source of truth:

```text
/lump/apps/agent-workflow
```

or:

```text
~/src/agent-workflow
```

Do not use `~/.local/bin` or agent skill directories as the source of truth.

## Install

```bash
cd /lump/apps/agent-workflow
./install.sh
```

## Installed locations

```text
~/.local/bin/agent-workflow
~/.config/agent-workflow/config.toml
~/.local/state/agent-workflow/runs/
~/.agents/skills/
~/.claude/skills/
```

XDG environment variables override config, state, and data roots.
