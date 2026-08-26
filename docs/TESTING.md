# Testing Strategy

The suite is intentionally layered and acceptance-first.

## Invariants

Fast deterministic tests protect serialization, contracts, path security, message replay, evaluation math, receipts, workflow transitions, and other security/durability/accounting boundaries that are more reliable as deterministic matrices than repeated full product journeys.

```bash
python -m pytest -q tests/invariants
```

## Acceptance journeys

Installed-product journeys exercise the public CLI, real filesystem behavior, Git worktrees, worker processes, durable messages, workflow resume, evaluation, review, benchmarks, MCP/plugins, preflight, and indexing.

```bash
python -m pytest -q tests/acceptance
```

## Consolidation policy

Keep a narrow test only when it protects a distinct security, durability, schema, replay, or accounting boundary that is difficult to prove economically end to end. Otherwise prefer one assertion-dense installed-product journey over multiple feature-specific journeys.

Do not add compatibility tests for removed terminal-era APIs and do not preserve test counts for their own sake.

## Release tests

Distribution tests validate wheel contents, installation, parser-derived command catalogs, release evidence, documentation synchronization, and repository/distribution boundaries.

```bash
python -m pytest -q tests/release
```

## Headless-core acceptance contract

The 0.8 release gate permanently protects these architectural outcomes:

- external preparation with no runtime host installed;
- Agent-Workflow-owned headless process-group lifecycle and terminal sealing;
- persist-first steer/progress/ack journeys;
- process/evidence-based supervision;
- workflow resume through durable Agent Run bindings and sealed predecessor inputs;
- headless benchmark execution;
- no interactive-runtime dependency in core configuration/source; and
- no Herdr dependency in core.

These requirements are enforced by the current invariant, acceptance, release, and repository-audit layers rather than by an implementation-phase checklist.

## Test-authority budget

`tests/test-authority.json` is the explicit suite-size and authority budget. Run:

```bash
python scripts/audit-test-suite.py
```

The audit prevents silent test proliferation, stale mock rationales, and duplicated low-value coverage. It is the current authority for suite-size limits; prose documentation intentionally does not duplicate exact counts that drift whenever tests are consolidated.

For a current inventory, count the test tree or use pytest collection in the working revision rather than relying on historical handoff numbers.
