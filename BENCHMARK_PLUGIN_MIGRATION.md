# Benchmark capability extraction

The historical comparative benchmark subsystem moved from Agent-Workflow core to the optional `agent-workflow-benchmark` plugin. Core retains generic sealed-run evaluation, scoring/review/lifecycle authority, and provider-neutral evaluation primitives.

## Install and enable

Install the plugin into the same environment as Agent-Workflow, then enable it explicitly:

```toml
[plugins]
enabled = ["agent-workflow-benchmark"]
```

The plugin contributes the top-level `benchmark` command dynamically. Verify the effective CLI with:

```bash
agent-workflow --help
agent-workflow benchmark --help
agent-workflow commands --format markdown
```

With `--no-plugins`, or when the plugin is not enabled, `benchmark` is not part of the CLI.

## Command migration

The former core surfaces map as follows:

```text
agent-workflow eval validate-benchmark  -> agent-workflow benchmark legacy-validate
agent-workflow eval benchmark-report    -> agent-workflow benchmark legacy-report
```

All current benchmark suite lifecycle commands live under `agent-workflow benchmark ...`. Benchmark schemas, bundled suites, targets, visual runtime assets, scoring/reporting code, and benchmark-specific documentation are owned by the plugin rather than Agent-Workflow core.
