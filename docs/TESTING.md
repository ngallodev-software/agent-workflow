# Testing strategy

The test suite is organized around behavior that an operator can observe. Test count is not a quality target; each retained test must protect a user journey, a security/state invariant, a release property, or an approved future capability.

## Test layers

### Acceptance journeys

`tests/acceptance/` builds a wheel from a clean source copy, installs it into an isolated virtual environment, and invokes the installed `agent-workflow` or `agent-workflow-mcp` executable as an external process.

The acceptance layer covers:

- installed CLI discovery, configuration, doctor, and actionable failures;
- prompt-pack scaffold, validation, and deterministic archive output;
- real Git worktree creation, listing, and removal;
- external executor launch, completion, failure, restart, review, acceptance, and interactive-agent reuse;
- bounded executor lifecycle and sealed evidence through the installed product; the compact process invariant matrix covers timeout/process-group cancellation, output caps, environment policy, and synthetic secret redaction;
- durable steer/watch/ack replay across process boundaries;
- structured provider-event collection into sealed normalized evidence;
- workflow validation, scheduling, restart/resume, approval, idempotency, sealing, and verification;
- authorized template expansion through the installed CLI;
- evaluation-plan validation and matched baseline/candidate comparison.

The deterministic fake executor and tmux shim are external executables, not mocked Python functions. They make process boundaries reproducible without requiring paid provider calls in the default suite.

### Invariant matrices

`tests/invariants/` is deliberately small. It directly exercises logic that needs exhaustive or adversarial coverage and would be expensive or nondeterministic to reproduce solely through end-to-end journeys:

- seal substitution, symlink, traversal, and read-only boundaries;
- append-only message ordering and fail-closed replay;
- scheduler dependency and parallelism rules;
- deterministic advisory routing that cannot override enforced policy;
- provider delta/cumulative/terminal accounting and duplicate identity rules;
- evaluation cohort identity and low-sample claims;
- the bounded JSON Pointer subset used for result binding.

Prefer one parameterized matrix to many nearly identical tests.

### Release checks

`tests/release/` validates distribution properties: repository release assets, JSON Schemas, shell syntax, agreement between documented primary commands and installed help, and the deterministic backlog/prompt-pack ownership audit. Static documentation and metadata checks belong here, not in behavioral unit tests.

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

`./scripts/release-check.sh` runs the default suite plus compile, shell, schema, release-asset, prompt-pack ownership, and documentation-drift checks. Apply the `release-drift-auditor` skill after parallel integration because deterministic checks cannot judge every semantic security overclaim.

## Current shape

The testing rewrite replaced 239 implementation-heavy tests across 46 files with a compact suite organized by product journeys and invariant matrices. Deleted tests are preserved in Git history and should not be restored merely to recover coverage numbers. Restore a behavior only by expressing it through the test layers above.
