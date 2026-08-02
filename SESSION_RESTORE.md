# Session restore and transfer checkpoint

**Project:** `agent-workflow`
**Current source version:** `0.7.8`
**Purpose:** restore a maintainer or implementation session from a portable source checkout without relying on a prior host, tmux server, virtual environment, or absolute path.

## Authority and recovery model

The Git checkout, immutable run artifacts, append-only journals, sealed receipts, and prompt-pack checksums are authority. Tmux panes, terminal capture, `status.json`, generated reports, and the SQLite index are observations or rebuildable projections.

Do not restore a session by copying a stale tmux layout, editing SQLite, or trusting an old terminal transcript. Recreate the environment from the source tree and verify durable evidence.

## Restore a source checkout

```bash
git status --short
git rev-parse --show-toplevel
cat VERSION
python3 --version
```

The expected active version for this checkpoint is `0.7.8`. When restoring a later revision, treat `VERSION` and the synchronized package/release metadata as authoritative rather than this document's example.

Install the base product from the checkout:

```bash
./install.sh
export PATH="$HOME/.local/bin:$PATH"
agent-workflow --version
agent-workflow doctor
```

Install optional profiles only where they are required:

```bash
./install.sh --extras mcp       # local read-only MCP adapter
./install.sh --extras eval      # optional evaluator integrations
```

Base installation does not require the MCP SDK or edit MCP client configuration. Jenkins and GitHub workflow files remain repository-only CI/CD assets and are not installed into the runtime environment.

## Verify repository state

```bash
python3 scripts/bump-version.py --check
python3 scripts/audit-release-assets.py
for pack in prompt-packs/*/pack.yaml; do
  agent-workflow pack validate "$(dirname "$pack")"
done
agent-workflow index rebuild
agent-workflow index verify --full [--review SESSION]
```

Run the focused or full test command appropriate to the work being resumed. Preserve unavailable live-provider, browser, tmux, or optional-MCP evidence as an explicit limitation rather than simulating it.

## Resume durable runs

List active runs and rebuild the disposable index if necessary:

```bash
agent-workflow index sync
agent-workflow index query runs
agent-workflow status RUN_ID --capture 80
agent-workflow watch RUN_ID --after 0 --timeout 30
```

Before interrupting, restarting, reviewing, or accepting a run, inspect its authoritative artifacts and verify its receipts. A query row or terminal capture is only a locator.

```bash
agent-workflow review RUN_ID --actor REVIEWER --reason "Independent evidence checked"
agent-workflow accept RUN_ID --actor REVIEWER --reason "Approved" --revision COMMIT_SHA
```

## Resume hierarchy authority review

The implemented hierarchy slice includes immutable fixed-depth contracts, capability and budget narrowing, append-only journals, idempotent imports, deterministic replay, and digest-sealed team/root receipts. It does **not** yet include hierarchy tmux topology, team runtime, team-lead scheduling, hierarchy messaging, or automated recovery.

Resume at `HIER-GATE-0` by reviewing and attacking the existing authority layer. Do not add runtime behavior until that gate is accepted.

## Resume modularization work

Completed behavior-preserving boundaries include:

- runtime environment and redaction policy behind `agent_workflow.process`;
- parser/bootstrap/output and major command-domain handlers behind `agent_workflow.cli`;
- SQLite schema, source discovery/stable reads, and query/report construction behind `agent_workflow.index_store`;
- session artifact construction and durable control/messaging behind `agent_workflow.sessions`;
- trusted plugin registration and digest-bound package resources.

Remaining candidates are deliberately narrower: session launch/observation/restart coordination, SQLite reconciliation/indexing, and runner stream/control/completion/sealing. Split one behavior-neutral slice at a time and preserve public facades and installed-product journeys.

## Package a transfer

For a source release or checkpoint:

```bash
python3 scripts/audit-release-assets.py
python3 scripts/bump-version.py --check
git status --short
```

Package only intended tracked changes, include a deletion manifest when needed, record validation commands and limitations, and verify the archive by extracting it into a clean directory. Never include credentials, local client configuration, mutable run state, browser profiles, private target repositories, or host-specific absolute paths.
