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

The shared contracts source is hosted on GitHub and installed directly by the
project dependency:

```bash
python -m pip install git+https://github.com/ngallodev-software/agent-workflow-spec-contracts.git
```

The source installer links skills into Codex by default. Opt into other
harness roots explicitly, for example `bash scripts/install-source.sh
--harnesses codex,claude,generic`; omitted legacy harnesses have only
Agent-Workflow-owned links removed.

Optional feature groups are declared in `pyproject.toml` for evaluation, statistics, completion generation, TypeSafe semantic decisions, benchmark visuals, and MCP. Enable bounded TypeSafe decisions with `python -m pip install 'agent-workflow[typesafe]'`; credentials remain external in `TYPESAFE_API_KEY`. The default source installer does not install or register MCP. To opt in explicitly from a checkout or release bundle:

```bash
bash scripts/install-mcp.sh
```

Use `--no-register` to install the MCP adapter without changing Codex or Claude configuration. Use `--unregister` to remove only Agent-Workflow-owned MCP entries.

## Windows 11

Install a built wheel from PowerShell:

```powershell
.\install.ps1 -Python python -Wheel .\dist\agent_workflow-*.whl
```

This installs the Python launcher and creates `%APPDATA%\agent-workflow\config.toml` without registering MCP, skills, or hooks. That avoids mixing MCP and CLI benchmark integrations; choose the benchmark cohort explicitly with `--codebase-memory-mode`.

## Configuration

Configuration is normally read from the XDG configuration path. The core config defines executor, Git, policy, security, plugin, workflow, and evidence behavior. It does not select an interactive terminal backend.

The shipped [`schemas/config.schema.json`](../schemas/config.schema.json) is the
public JSON Schema for the configuration document and is installed with the
other schemas. Runtime TOML parsing and policy validation remain owned by
`src/agent_workflow/config.py`; the schema is a contract/reference check, not a
second configuration validator.

## External plugin installation and recovery

Install an external plugin into the same Python environment as
`agent-workflow`, using the immutable release wheel supplied by the plugin
publisher. This host-side flow consumes a verified local release artifact; external plugins remain for independent extensions. TypeSafe is no longer one of them; it is an optional built-in semantic provider.

Check the installed distribution, plugin version, configured enablement, and
load/API result before using plugin commands:

```bash
agent-workflow plugins list --json
agent-workflow doctor
```

If discovery or compatibility fails, suppress configured plugins and recover
the core host while investigating the artifact:

```bash
agent-workflow --no-plugins plugins list
agent-workflow --no-plugins doctor
```

For external-plugin rollback, disable the affected plugin in `[plugins].enabled` (or use `--no-plugins`) and restore the previously qualified plugin wheel. TypeSafe rollback is simply `decision_policy.mode = "deterministic"`; the SDK remains optional and credentials remain outside configuration.

## Tagged bootstrap install

For a published release, pin the release explicitly. For version `0.10.2`:

```bash
curl -fsSL https://github.com/ngallodev-software/agent-workflow/releases/download/v0.10.2/install.sh | \
  sh -s -- --version v0.10.2
```

The version is intentional: the 0.9 line builds on the breaking Agent Run/headless-core rewrite and does not carry terminal-host compatibility.

## Repository-only CI assets

Jenkins and local server-job definitions are excluded from installed wheels and platform runtime bundles. They remain source-repository maintenance assets only.
