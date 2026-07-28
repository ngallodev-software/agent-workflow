# Two-way messaging blocker-clearance execution — 2026-07-28

## Decision

The blocker-clearance prompt was executed against the `0.2.5` source snapshot
uploaded on 2026-07-28. The repository is **not yet authorized to start
`MSG-001`**. `HARD-004` and `HARD-005` remain `in-review`; neither has the
complete, independently accepted, sealed evidence required by the prompt.

This result preserves the canonical dependency model rather than advancing a
messaging ticket from implementation prose, mutable status, or incomplete
exports.

## Baseline validation

| Check | Result |
|---|---|
| `python3 scripts/audit-release-assets.py` | pass — `release assets: valid` |
| deterministic-enforcement-foundations pack | pass — 3 phases, 5 tasks |
| execution-isolation-and-secrets pack | pass — 3 phases, 4 tasks |
| public-beta-trust-and-release pack | pass — 2 phases, 5 tasks |
| orchestrator-two-way-messaging pack | pass — 6 phases, 10 tasks |
| source snapshot Git metadata | unavailable — archive contains no `.git` |
| codebase-memory-mcp | unavailable in this execution environment |

The missing `.git` directory prevents verification of source commit identity,
integrated diffs, worktree scope, and independent reviewer ancestry inside this
snapshot. No commit or worktree claim is inferred from filenames or prose.

## Blocker graph before

```text
HARD-004 (in-review) ───────────────┐
                                    ├─> MSG-001 (blocked)
DEC-001 + HARD-002 (accepted) ──────┘

HARD-005 (in-review) ──┐
HARD-008 (blocked) ─────┼─> HARD-006 (blocked)
HARD-004 (in-review) ───┼─> HARD-007 (blocked)
                         └─> later messaging phases

HARD-004 + HARD-007 + HARD-008 + BKL-001 + HARD-001
    └─> BKL-002 (ready but gated)
```

## Evidence review

### HARD-004

Implementation evidence states that immutable launch authority is integrated,
but expressly does not claim phase-gate acceptance. The exported assessment
for the earlier HARD-004 run reports a blocked completion and omits the artifacts
needed for portable lifecycle verification, including launch authority,
provider evidence, execution metrics, source baseline, completion collection,
and evaluation evidence.

The strict future journey
`tests/future/test_deterministic_authority_journeys.py::test_hard_004_status_projection_cannot_change_launch_or_receipt_authority`
is still an explicit placeholder expected failure. It does not exercise the
installed product and cannot serve as acceptance evidence.

**Disposition:** remain `in-review`.

Required clearance:

1. Run the installed-wheel launch/restart/evaluation/projection-tamper journey
   from a real Git checkout.
2. Export the complete run, including the immutable launch contract, provider
   stream, completion collection, evaluation plan/report/collection, final
   receipt, lifecycle receipt, and source baseline.
3. Bind the same run/ticket/pack/source/evidence digests in the evaluation
   ledger.
4. Obtain an independent reviewer disposition and rerun `FOUND-GATE-01`.

### HARD-005

The existing sealed run supports metadata/no-follow criteria but the repository
itself records installed stdio MCP acceptance as unverified. The current
execution host cannot install or import `mcp==1.28.1`; therefore the installed
stdio journey could not be reproduced. This is an environment limitation, not
proof of acceptance or rejection of the implementation.

**Disposition:** remain `in-review`.

Required clearance:

1. Build and install the wheel with the pinned MCP extra in a dependency-enabled
   environment.
2. Run `tests/acceptance/test_mcp_product_journeys.py` over stdio.
3. Verify bounded metadata-only reads, no-follow behavior, stable errors,
   receipt summaries, and absence of secret bodies and raw local paths.
4. Seal and independently accept the run, then rerun `FOUND-GATE-01`.

## Test results from this snapshot

A source-level run excluding MCP collection produced:

- 69 passing tests;
- 5 strict expected failures representing approved unfinished work;
- 1 failure caused by absent `.git` metadata in the source archive;
- 26 setup errors caused by the unavailable pinned MCP package in the isolated
  installed-product fixture.

The expected failures include HARD-004, MSG-005, BKL-002, BKL-004, and
MCP-003/HARD-007. Because the installed-product fixture installs MCP for all
acceptance modules, the missing package prevents unrelated installed-product
journeys from running on this host as well.

## Blocker graph after

```text
UNCHANGED AUTHORITY STATE

HARD-004 (in-review: complete sealed independent disposition missing)
    └─> MSG-001 remains blocked

HARD-005 (in-review: installed stdio evidence missing)
    └─> FOUND-GATE-01 cannot be accepted

FOUND-GATE-01 rejected/not reproducible from exported evidence
    ├─> HARD-007 remains blocked
    ├─> HARD-008 remains the next legal hardening implementation lane
    └─> no messaging implementation phase is executable yet
```

## Delegation and lifecycle evidence

No agent-workflow implementation session was launched. The supplied artifact is
not a Git checkout, codebase-memory-mcp was unavailable, and the acceptance
prerequisites were not present. Consequently there are no truthful session IDs,
worktree paths, model assignments, pane closeout receipts, commits, or changed
implementation paths to report.

## Next executable work

The next legal implementation lane is `HARD-008`, because its declared
prerequisite `HARD-001` is accepted. In parallel, review-only evidence recovery
for `HARD-004` and `HARD-005` may proceed in a real Git checkout with the pinned
MCP dependency available. `MSG-001` may begin only after `HARD-004` receives an
accepted independent sealed disposition.
