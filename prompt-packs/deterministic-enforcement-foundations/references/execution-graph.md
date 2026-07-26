# Execution graph

```mermaid
flowchart TB
  subgraph P0[Phase 0 — bounded execution and artifact integrity]
    HARD_001[HARD-001]
    HARD_002[HARD-002]
  end
  subgraph P1[Phase 1 — immutable authority and MCP read boundary]
    HARD_004[HARD-004]
    HARD_005[HARD-005]
  end
  subgraph P2[Phase 2 — independent foundation gate]
    FOUND_GATE_01[FOUND-GATE-01]
  end
  HARD_001 --> HARD_004
  HARD_002 --> HARD_004
  HARD_002 --> HARD_005
  HARD_004 --> FOUND_GATE_01
  HARD_005 --> FOUND_GATE_01
```

Tickets without a dependency edge may run concurrently in separate worktrees. Gate tasks run only after all incoming dependencies are accepted and integrated.
