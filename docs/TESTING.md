# Testing strategy

The test suite is organized around behavior that an operator can observe. Test count is not a quality target; each retained test must protect a user journey, a security/state invariant, a release property, or an approved future capability.

## Test layers

### Acceptance journeys

`tests/acceptance/` builds a wheel from a clean source copy, installs it into an isolated virtual environment, and invokes the installed `agent-workflow` or `agent-workflow-mcp` executable as an external process.

The acceptance layer covers:

- installed CLI discovery, configuration, doctor, and actionable failures;
- schema-versioned configuration, unknown-key rejection, trusted-path warnings/failures, and executor compatibility identity through the installed doctor journey;
- prompt-pack scaffold, validation, and deterministic archive output;
- real Git worktree creation, listing, and removal;
- external executor launch, completion, failure, restart, review, acceptance, and interactive-agent reuse;
- bounded executor lifecycle and sealed evidence through the installed product; the compact process invariant matrix covers timeout/process-group cancellation, output caps, environment policy, and synthetic secret redaction;
- durable steer/watch/ack replay across process boundaries;
- structured provider-event collection into sealed normalized evidence;
- workflow validation, scheduling, restart/resume, approval, idempotency, sealing, and verification;
- authorized template expansion through the installed CLI;
- deterministic evaluation/benchmark template rendering, plan and manifest validation, sealed scoring/collection, benchmark reports, evidence-ledger rows, archive plans, and matched baseline/candidate comparison.
- the comparative benchmark source-level journey: frozen fixture identity, subscription/API authentication boundaries, operating-policy validation, isolated coordinator/arm and retry worktrees, synchronized paired phases, usage/cost/timing evidence, visual runtime attestation, deterministic scoring/statistics, treatment-blinded review, composite reporting, digest verification, and cleanup;

The deterministic fake executor and tmux shim are external executables, not mocked Python functions. They make process boundaries reproducible without requiring paid provider calls in the default suite.

### Invariant matrices

`tests/invariants/` is deliberately small. It directly exercises logic that needs exhaustive or adversarial coverage and would be expensive or nondeterministic to reproduce solely through end-to-end journeys:

- seal substitution, symlink, traversal, and read-only boundaries;
- append-only message ordering and fail-closed replay;
- scheduler dependency and parallelism rules;
- deterministic advisory routing that cannot override enforced policy;
- provider delta/cumulative/terminal accounting and duplicate identity rules;
- evaluation template/schema semantics, unavailable-data handling, cohort identity drift, deterministic archive inputs, and low-sample claims;
- the bounded JSON Pointer subset used for result binding;
- health collection, semantic-progress calculation, terminal-capture redaction/change detection, permission transitions, incident deduplication, projection repair, and remediation ceilings.

Prefer one parameterized matrix to many nearly identical tests.

### Supervisor and recovery journeys

Supervisor coverage must prove behavior through the installed CLI where host facilities are available. Required journeys include a progressing run, a live process with no semantic progress, an interactive permission wait, output-capture exhaustion, process/pane loss, corrupt mutable projection, missed wake/replay, one-probe idempotence, explicit interrupt/restart opt-in, and supervisor restart. Every journey must assert durable incident/remediation evidence and retry lineage rather than merely inspect console text.

Low-level tests may inject deterministic health samples or fake tmux/process observations, but they may not make mutable status or pane text authoritative. Live host/executor matrices remain gated under `SUP-006`.

### SQLite projection journeys

`tests/invariants/test_sqlite_index.py` exercises deterministic rebuild, unchanged-run incremental sync, curated run/performance queries, query-freshness envelopes, workflow node/edge materialization, same-size/same-mtime source-change detection, source tamper detection, corrupt-run quarantine, mixed-currency nulling, and the invariant that terminal bodies never enter the database. Installed-product validation must additionally build a wheel, invoke the public `agent-workflow index` commands, delete the database, rebuild it, and compare query results and source provenance.

Migration tests start from every supported prior schema version. Corruption tests must distinguish a damaged SQLite projection—which is disposable—from damaged authoritative evidence, which must fail closed and remain untouched. Performance work must use generated multi-run fixtures and publish source-count, event-count, database-size, sync-time, rebuild-time, and query-latency evidence rather than relying on unit-level timing assertions.

### Release checks

`tests/release/` validates distribution properties: repository release assets, JSON Schemas, shell syntax, agreement between documented primary commands and installed help, deterministic backlog/prompt-pack ownership, release-policy/lock synchronization, and the durable release-evidence path. Static documentation and metadata checks belong here, not in behavioral unit tests.

### Future acceptance specifications

`tests/future/` contains approved backlog behavior expressed as black-box journeys. These tests are `xfail(strict=True)`: they execute and expose the current gap, while an unexpected pass fails the suite until the test is reviewed and promoted into `tests/acceptance/`.

A future test must name an approved backlog item and specify an operator-visible result. Parser shape, private helper calls, or speculative interfaces are not acceptable future tests.

### Plugin boundary

The plugin host has compact invariants for import-free discovery, strict API compatibility, duplicate-registration rollback, core-command collision rejection, and `--no-plugins`. Its acceptance journey builds a separate fixture-plugin wheel, installs it beside the built product wheel, proves that disabled metadata discovery does not import the module, executes an explicitly enabled top-level command, verifies command-catalog provenance, and proves core-only recovery.

## Live compatibility

`tests/live/` is opt-in because it requires host resources or paid services. It is intended for real tmux, Codex, Claude, and MCP compatibility checks before release. Set the documented environment switches and run:

```bash
pytest -m live
```

## Rules for new tests

A proposed test should answer at least one of these questions:

1. What complete user action would break without this test?
2. What security, replay, accounting, or durability invariant requires exhaustive isolated coverage?
3. What approved backlog capability does this executable future specification define?
4. What distributable release property does this check protect?

Do not add a test merely because a function, branch, parser field, dictionary shape, or prose fragment exists. Avoid private imports and mocks unless the test is an invariant that cannot be exercised deterministically through a public boundary.

When a defect is discovered, first extend the nearest end-to-end journey. Add a narrow invariant only when the defect belongs to a general security/state matrix.

## Test authority and drift budgets

`tests/test-authority.json` is the executable inventory for the suite. It records the authority and rationale for every invariant file, any narrowly approved mock or private-import exception, per-file function ceilings, layer file/function/collection ceilings, subprocess and wheel-build site ceilings, and the default-suite runtime ceiling.

Run the audit before and after test changes:

```bash
python3 scripts/audit-test-suite.py
```

The policy is a drift ceiling, not a coverage target. Deleting redundant coverage does not require restoring the old count. Raising any ceiling requires a reviewable explanation of the complete user journey or isolated invariant that cannot be protected by existing authority. New invariant files fail until they are explicitly inventoried. Direct imports from `agent_workflow.cli_handlers`, `agent_workflow.cli_parser`, or `agent_workflow.cli_runtime` are forbidden in invariants; those behaviors belong at the installed executable boundary.

The 2026-08-02 consolidation removed private CLI dispatch/decomposition tests and moved manifest-native pack validation, repository closeout, evidence repair, and parser/runtime routing to installed-product journeys. The invariant layer decreased from 52 files and 320 collected cases to 35 files and 247 collected cases; preserving the LAN live-review regression adds one accepted default-suite case, so the current default ceiling is 341 cases. The retained ceilings are intentionally below the prior shape and are enforced mechanically.

`release-check.sh` runs the authority audit before pytest, then re-runs it against JUnit evidence. The post-run audit records total test count and duration in `build/release-evidence/test-suite-audit.json`; the current default-suite runtime ceiling is 420 seconds, based on a measured 332.98-second successful full gate plus bounded scheduling headroom. Static budgets also prevent silent multiplication of subprocess call sites or wheel builds.

## Commands

```bash
# Default release-development environment and gate
./scripts/bootstrap-dev.sh
python3 scripts/audit-test-suite.py
.venv/bin/python -m pytest -q
./scripts/release-check.sh
# Public-release enforcement: exits 3 while governance/compatibility blockers remain
AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1 ./scripts/release-check.sh

# Behavioral acceptance only
.venv/bin/python -m pytest tests/acceptance

# Security/state/accounting matrices
.venv/bin/python -m pytest tests/invariants

# Static distribution checks
.venv/bin/python -m pytest tests/release

# Approved future specifications
.venv/bin/python -m pytest tests/future

# Real host/provider compatibility
AGENT_WORKFLOW_LIVE_TMUX=1 .venv/bin/python -m pytest -m live
AGENT_WORKFLOW_LIVE_EXECUTOR=codex .venv/bin/python -m pytest -m live
AGENT_WORKFLOW_LIVE_EXECUTOR=claude .venv/bin/python -m pytest -m live
```

`./scripts/release-check.sh` runs the default suite plus compile, shell, schema, release-asset, prompt-pack ownership, and documentation-drift checks. It writes `pytest-junit.xml`, `sbom.cdx.json`, `build-provenance.json`, and `release-evidence.json` under `build/release-evidence` unless `AGENT_WORKFLOW_RELEASE_EVIDENCE_DIR` overrides the destination. Open release-policy blockers are recorded by default and enforced when `AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1`. Apply the `release-drift-auditor` skill after parallel integration because deterministic checks cannot judge every semantic security overclaim.

The default suite uses synthetic custom executors in local mode. Live compatibility
checks should run `doctor` and a read-only launch on the supported provider
executors; no paid provider task is part of the default suite.

## Current implementation boundaries

Focused invariant and installed-wheel journeys cover:

- trusted-plugin import suppression, atomic registration, collision handling, digest-bound package resources, traversal/tamper rejection, and a separately installed fixture plugin;
- hierarchy contracts, capability/budget narrowing, append-only journals, idempotent imports, deterministic replay, and mutation-sensitive team/root receipts;
- installed CLI routing and stable public behavior without private handler/parser tests;
- SQLite source/query, session-control, and evidence boundaries only where adversarial state matrices are cheaper than installed journeys;
- distribution exclusion of Jenkins/GitHub CI assets and fail-safe optional MCP installation.

A passing hierarchy authority test does not claim team runtime, tmux topology, scheduling, or recovery. Those remain future/gated journeys.

## Current shape

The suite is organized by product journeys and invariant matrices rather than test-count targets. Deleted implementation-coupled tests are preserved in Git history and should not be restored merely to recover coverage numbers. Restore a behavior only by expressing it through the test layers above. The authority policy is reviewed whenever a legitimate new test changes a ceiling; it must never be increased merely because a new helper or branch exists. Implemented future specifications, such as HARD-004, must graduate into acceptance/invariant coverage instead of remaining strict expected failures.
