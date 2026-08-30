# Installation

## Requirements

- Python 3.11+
- Git
- the coding-agent/provider executables you choose to configure

No interactive runtime host is required for core operation.

## Development install

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
agent-workflow --version
agent-workflow doctor
```

## Wheel install

```bash
python -m build
python -m pip install dist/agent_workflow-*.whl
```

Optional feature groups are declared in `pyproject.toml` for evaluation, statistics, completion generation, benchmark visuals, and MCP.

## Configuration

Configuration is normally read from the XDG configuration path. The core config defines executor, Git, policy, security, plugin, workflow, and evidence behavior. It does not select an interactive terminal backend.

## Tagged bootstrap install

For a published release, pin the release explicitly. For version `0.9.1`:

```bash
curl -fsSL https://github.com/ngallodev-software/agent-workflow/releases/download/v0.9.1/install.sh | \
  sh -s -- --version v0.9.1
```

The version is intentional: the 0.9 line builds on the breaking Agent Run/headless-core rewrite and does not carry terminal-host compatibility.

## Repository-only CI assets

Jenkins and local server-job definitions are excluded from installed wheels and platform runtime bundles. They remain source-repository maintenance assets only.
