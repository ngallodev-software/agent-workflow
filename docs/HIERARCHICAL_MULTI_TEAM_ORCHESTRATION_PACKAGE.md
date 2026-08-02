# Hierarchical multi-team orchestration package

## Delivered design

The package introduced the root-orchestrator → team-lead → worker design. The current source implements HIER-001 contract authority and the complete HIER-002 durable-authority slice: journals, replay, and digest-sealed team/root receipts. HIER-GATE-0 review and all hierarchy runtime behavior remain gated.

Included:

- complete architecture and workflow design;
- `DEC-005` for maintainer approval, avoiding the existing benchmark-policy `DEC-002`;
- tmux topology, authority, messaging, and recovery diagrams;
- canonical backlog ownership for `HIER-001` through `HIER-008`;
- an explicit critical path, external prerequisite gates, and optional terminal-adapter branch in `docs/BACKLOG.md`;
- a validated four-phase prompt pack with eight implementation tickets and five independent gate tickets;
- architecture and prompt-pack index updates;
- an independent verification record for the original design overlay;
- current `agent_workflow.hierarchy` contract, journal/replay, and receipt APIs; strict schemas; read-only installation; tamper/later-append verification; and installed-wheel tests for HIER-001 and HIER-002.

## Dependency order

The durable authority lane may start while the existing foundations are being accepted:

1. Approve `DEC-005`.
2. Run independent `HIER-GATE-0` review over the implemented HIER-001 contracts and HIER-002 journals, replay, and receipts.
3. In parallel, complete the existing acceptance gates: `PROC-006` before `HIER-003`; `MSG-001`, `PROC-001`, and `PROC-002` before `HIER-005`; `BKL-002` before `HIER-006`.
4. Execute the core path: `HIER-003` → `HIER-GATE-1` → `HIER-005` → `HIER-006` → `HIER-GATE-2` → `HIER-007` → `HIER-008` → `HIER-GATE-3`.
5. After `HIER-003`, `HIER-004` → `HIER-GATE-1A` may run as an optional parallel branch and does not block the core path.

## Validation command

```text
PYTHONPATH=src python -m agent_workflow pack validate \
  prompt-packs/hierarchical-multi-team-orchestration
```

The corrected package contains four phases and thirteen tasks. See `HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_VERIFICATION.md` for the recorded verification results.
