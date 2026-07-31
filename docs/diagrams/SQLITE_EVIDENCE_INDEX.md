# SQLite evidence index diagrams

These diagrams accompany [SQLite evidence index architecture](../SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md).

## Authority and projection flow

```mermaid
flowchart TB
  subgraph AUTH[Authoritative evidence plane]
    A1[Immutable launch and source contracts]
    A2[Append-only run and workflow journals]
    A3[Sealed completion and lifecycle receipts]
  end

  R[No-follow, schema-validating reconciler]
  S[(Rebuildable SQLite projection)]
  Q1[Operational CLI]
  Q2[Supervisor fleet view]
  Q3[Performance and reliability analysis]

  A1 --> R
  A2 --> R
  A3 --> R
  R --> S
  S --> Q1
  S --> Q2
  S --> Q3
  S -. cannot authorize or rewrite .-> AUTH
```

## Run reconciliation state machine

```mermaid
stateDiagram-v2
  [*] --> Discovered
  Discovered --> Skipped: fingerprint unchanged and current
  Discovered --> Reading: new, moved, changed, or forced
  Reading --> Validating
  Validating --> Replacing: sources valid
  Replacing --> Current: transaction committed
  Validating --> ErrorProjection: malformed, unsafe, or seal-invalid
  ErrorProjection --> Reading: later source change or forced rebuild
  Current --> Reading: source fingerprint changes
  Current --> Pruned: source run no longer exists
  Pruned --> [*]
```

## Trust boundary

```mermaid
flowchart LR
  U[Untrusted or probabilistic executor]
  E[Per-run evidence writer]
  F[Validated files and sealed receipts]
  I[Deterministic indexer]
  D[(SQLite)]
  C[Read-only consumers]
  H[Human / authenticated authority]

  U --> E --> F --> I --> D --> C
  H -->|permission, review, acceptance| F
  D -. no authority edge .-> H
```
