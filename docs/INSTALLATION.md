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

The base install includes the CLI and core authority/runtime dependencies. Install the optional local MCP adapter only where needed:

```bash
./install.sh --extras mcp
```

MCP configuration is registered only when the `mcp` extra is requested. Jenkins repository automation is not copied into the environment.

This installs the package and its core Python dependencies in editable user
mode, then wires the launcher, skills, man pages, schemas, evaluation assets,
and active prompt packs. The core package includes the pinned MCP SDK because
the installed `agent-workflow-mcp` entry point requires it. To install optional
integrations, use `./install.sh --extras eval,stats` or
`./install.sh --extras all`.

The installer does not require an activated virtual environment. It uses the
selected `python3` interpreter, bootstraps pip with `ensurepip` when available,
and otherwise reports the exact interpreter that needs pip. To select another
host Python, use `./install.sh --python /path/to/python3`.

```bash
agent-workflow-mcp --help
```

The installer registers the local stdio server as `agent-workflow` in the
user-level Codex and Claude Code configuration on every normal install.
Existing entries with that name are preserved. The `mcp` extra remains
available as a compatibility alias.

## Install a tagged release

Linux and macOS users can install a published wheel through the POSIX
bootstrap. Windows is intentionally unsupported; use WSL2, which selects the
Linux/WSL2 release bundle after explicit detection.

Pass the same immutable tag named by the raw GitHub URL. The bootstrap rejects
missing or non-semantic release references, downloads only from that tag's
release assets, and verifies `SHA256SUMS` before extracting or invoking pip:

```sh
curl -fsSL https://github.com/ngallodev-software/agent-workflow/raw/v0.7.7/install.sh \
  | sh -s -- --version v0.7.7
```

The release contract requires Python 3.11+, `curl`, a SHA-256 tool, and `tar`.
The bootstrap recognizes Linux `x86_64`/`arm64`, WSL2 `x86_64`/`arm64`, and
macOS `x86_64`/`arm64`; unsupported hosts stop before download. A checksum
failure stops before extraction and installation. The trust boundary is the
immutable Git tag plus the separately published checksum manifest; checksum
verification detects transfer corruption but does not replace signed release
attestation, which remains a future release gate.

For an already downloaded platform bundle, extract it and run its bundled
installer, then use the matching `uninstall.sh` to remove the wheel and owned
assets:

```sh
tar -xzf agent-workflow-0.7.7-linux.tar.gz
cd agent-workflow-0.7.7-linux
./install.sh --wheel agent_workflow-0.7.7-py3-none-any.whl
./uninstall.sh
```

Bundles are labelled `linux`, `wsl2`, or `macos`; native Windows bundles are
not published. The release installer preserves unrelated user configuration,
skill links, and locally modified man pages.

The MCP release is stdio-only. It exposes bounded run resources and
prompt-pack validation; it does not expose shell execution, raw tmux control,
destructive lifecycle tools, or HTTP transport.

The searchable evidence index uses Python's standard-library SQLite support; it does not install or require a database service. Create it after installation with `agent-workflow index rebuild`.

## Installed locations

```text
~/.local/bin/agent-workflow
~/.config/agent-workflow/config.toml
~/.local/share/agent-workflow/schemas/
~/.local/share/agent-workflow/evals/
~/.local/share/agent-workflow/prompt-packs/
~/.local/share/man/man1/
~/.local/state/agent-workflow/runs/
~/.local/state/agent-workflow/index/agent-workflow.sqlite3
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

XDG environment variables override config, state, and data roots. The SQLite file is a rebuildable projection; preserve the run/archive directories and sealed receipts as the actual evidence backup.

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
The pipeline uses the core MCP dependency; use `--extras eval` only when the
host is intentionally dedicated to the optional evaluator stack.


## Repository-only CI/CD assets

`Jenkinsfile`, `scripts/jenkins-local-job.sh`, `scripts/jenkins-local-job.xml`, and `.github/workflows/` are development and release-automation source. They are intentionally excluded from installed wheels and platform runtime bundles. A Jenkins deployment may invoke `./install.sh --extras mcp` on a development host when its job needs MCP acceptance coverage; that does not make MCP or Jenkins part of the default runtime install.
