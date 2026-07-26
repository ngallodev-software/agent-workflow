# Execution graph

```mermaid
flowchart TB
  subgraph P0[Phase 0 — trust, drift, supply chain, and compatibility]
    HARD_007[HARD-007]
    HARD_009[HARD-009]
    HARD_010[HARD-010]
    REL_003[REL-003]
  end
  subgraph P1[Phase 1 — public-preview decision gate]
    REL_004[REL-004]
  end
  HARD_007 --> REL_004
  HARD_009 --> REL_004
  HARD_010 --> REL_004
  REL_003 --> REL_004
```

Tickets without a dependency edge may run concurrently in separate worktrees. Gate tasks run only after all incoming dependencies are accepted and integrated.
