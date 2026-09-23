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

For local development where Agent-Workflow and external plugins share one virtualenv,
prefer the repository helper:

```bash
bash scripts/build-install.sh
```

It resolves the target virtualenv from `--venv`, `AGENT_WORKFLOW_VENV`,
`VIRTUAL_ENV`, the active Python interpreter, the repository `.venv`, or the
current Agent-Workflow launcher, in that order. It does not create a virtualenv
and does not install into the user Python environment.

The helper removes an editable Agent-Workflow install from the selected venv,
builds a wheel from this checkout, installs that wheel back into the same venv
with `--no-deps`, and verifies package/version/launcher ownership plus exact
schema filename and SHA-256 parity. It also rejects benchmark schemas in the core
wheel and preserves an already installed benchmark plugin in the same venv.

Audit an existing wheel install without rebuilding:

```bash
bash scripts/build-install.sh --verify-only
```

Use an explicit target when needed:

```bash
bash scripts/build-install.sh --venv /path/to/agent-workflow/.venv
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

For a published release, pin the release explicitly. For version `0.11.9`:

```bash
curl -fsSL https://github.com/ngallodev-software/agent-workflow/releases/download/v0.11.9/install.sh | \
  sh -s -- --version v0.11.9
```

The version is intentional: the 0.9 line builds on the breaking Agent Run/headless-core rewrite and does not carry terminal-host compatibility.

## Repository-only CI assets

Jenkins and local server-job definitions are excluded from installed wheels and platform runtime bundles. They remain source-repository maintenance assets only.


## Isolated development runtime

The wheel build/install helper uses a venv-local XDG runtime while it runs:

```text
<venv>/.xdg/config
<venv>/.xdg/state
<venv>/.xdg/data
```

For an interactive shell, opt into the same environment by sourcing:

```bash
source scripts/dev-env.sh on
```

This sets `VIRTUAL_ENV`, `AGENT_WORKFLOW_VENV`, `AGENT_WORKFLOW_BIN`, `PATH`,
`XDG_CONFIG_HOME`, `XDG_STATE_HOME`, and `XDG_DATA_HOME`. The helper seeds or
refreshes the venv-local Agent-Workflow config and rewrites only `[paths].worktree_root`
and `[paths].state_root` to the isolated venv locations.

Restore every prior shell value, including previously unset variables, with:

```bash
source scripts/dev-env.sh off
```

The benchmark smoke runner performs the same isolation in its child process, so its
XDG changes disappear automatically when the smoke script exits.


## Complete shared development stack

For the benchmark/SpecGen development environment, install the entire qualified
stack into one existing virtualenv:

```bash
export TYPESAFE_API_KEY='...'
bash scripts/build-install-all.sh --venv /path/to/agent-workflow/.venv
```

Default sibling source layout:

```text
../agent-workflow-spec-contracts
../agent-workflow-comparative-eval
../specgen-aw
../agent-workflow-benchmark
```

Override any checkout explicitly with `--contracts-source`,
`--comparative-eval-source`, `--specgen-source`, or
`--benchmark-source`.

A normal full-stack run first updates all five source repositories with
`git pull --ff-only`. The helper fails closed on dirty checkouts, detached
HEADs, missing upstreams, or divergence; it never switches branches, resets,
cleans, stashes, rewrites remotes, or changes authentication configuration.
Agent-Workflow itself is pulled last and the installer then re-execs the freshly
pulled script before version checks/builds.

Authentication is deliberately not managed by these scripts. Each update is an
ordinary `git pull --ff-only`, so an HTTPS remote uses the same existing Git
credential helper/session it would use from your shell, while SSH remotes use
the same existing SSH configuration. The scripts do not set token variables,
disable credential helpers, inject askpass programs, or rewrite remote URLs.

Useful update modes:

```bash
# Update all stack repositories and exit.
bash scripts/build-install-all.sh --pull-only

# Build the exact checked-out source without Git/network mutation.
bash scripts/build-install-all.sh --no-pull --venv /path/to/.venv

# Verify the installed stack without pulling or rebuilding.
bash scripts/build-install-all.sh --verify-only --venv /path/to/.venv
```

The lower-level update helper is also directly available:

```bash
bash scripts/git-pull-all.sh --help
```

The installer builds local wheels and installs this exact stack:

```text
specgen-agent-workflow-contracts  0.2.1
agent-workflow                    0.11.9
agent-workflow-comparative-eval   0.1.0
specgen                           0.2.8
agent-workflow-benchmark          0.3.5
typesafe-sdk                      0.6.0
```

The generated venv-local config enables `agent-workflow-spec` and
`agent-workflow-benchmark`, selects the built-in TypeSafe semantic provider,
and sets `decision_policy.mode = "comparative"`.
`agent-workflow-comparative-eval` is a shared library and is intentionally not
listed as a plugin.

The verification gate requires `TYPESAFE_API_KEY`, a compatible comparative
runtime, both plugins loaded, SpecGen targeting Agent-Workflow 0.11.9,
`pip check` success, and direct `codex` execution rather than the obsolete
`agent-workflow-codex` wrapper.

Audit the already-installed stack without rebuilding:

```bash
export TYPESAFE_API_KEY='...'
bash scripts/build-install-all.sh --verify-only --venv /path/to/.venv
```
