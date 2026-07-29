# Deterministic foundation gate review — 2026-07-28

## Decision

`FOUND-GATE-01` is accepted for the current integrated tree at `5f2b9dc`.
The prior rejection was against revision `8f7cdd4` and explicitly named the
then-missing HARD-001, HARD-002, HARD-004, and HARD-005 controls. Those findings
are stale for the current tree: the implementations are integrated, HARD-004
and HARD-005 have current review records, and the shared acceptance gates now
reproduce in the project environment.

## Prerequisites

| Ticket | Current evidence |
| --- | --- |
| HARD-001 | Completed and independently accepted at `91f5ff3` |
| HARD-002 | Completed and independently accepted at `5d689b6` |
| HARD-004 | Current review and closure at `ef6393e`; [review](HARD-004-REVIEW-20260728.md) |
| HARD-005 | Current review and closure at `8fde4c3`; [review](HARD-005-REVIEW-20260728.md) |

## Gate commands

| Command | Result |
| --- | --- |
| `rtk .venv/bin/python -m pytest -q` | 103 passed, 2 skipped, 5 strict xfailed |
| MCP installed stdio journey | 7 passed |
| HARD-008 trust/config acceptance slices | 14 passed |
| Security/durable/sealed slices | 18 passed |
| `rtk .venv/bin/python scripts/audit-release-assets.py` | release assets valid |
| Four required active-pack validations | all valid |

The strict xfails are the explicitly planned future journeys for HARD-004,
MSG-005, BKL-004, MCP-003/HARD-007, and BKL-002. They do not represent a
failure of the accepted foundation scope.

## Review findings

- Authority: current launch-contract v2, projection repair, restart, and
  receipt-digest checks are covered by the HARD-004 review and focused suite.
- MCP privacy/path: current stdio and invariant suites verify metadata-only
  output, no-follow replacement rejection, receipt integrity, bounds, and
  opaque errors.
- Config/executor trust: current HARD-008 acceptance slices pass ownership,
  unknown-policy, executable identity, and sanitized-environment checks.
- Ownership/release drift: release audit and all four pack validations pass;
  no new task ownership or checksum collision was found.

The gate decision is a coordinator review of current source and rerun gates.
It does not rewrite the older rejected run or invent a missing lifecycle
receipt from that run.

