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

### Live compatibility

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

## Commands

```bash
# Default release-development environment and gate
./scripts/bootstrap-dev.sh
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

## Current shape

The testing rewrite replaced 239 implementation-heavy tests across 46 files with a compact suite organized by product journeys and invariant matrices. Deleted tests are preserved in Git history and should not be restored merely to recover coverage numbers. Restore a behavior only by expressing it through the test layers above.
