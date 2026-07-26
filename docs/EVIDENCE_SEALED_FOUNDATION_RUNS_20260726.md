# Sealed foundation-run evidence — 2026-07-26

This report records the authoritative agent-workflow lifecycle evidence used for the 0.2.3 integration. Terminal output is not treated as proof. Every listed run has a valid completion collection, exit code 0, a sealed final receipt, and no live tmux pane.

| Ticket | Session | Completion | Final receipt SHA-256 | Sealed artifacts | Evaluation |
|---|---|---|---|---:|---|
| HOOK-DOGFOOD-001 | `hook-dogfood-001-20260726` | valid / completed | `554ecf1eb77f82dccbf2bf8258b3154b732df14d6482803a55509dfa84d8f256` | 18 | none attached |
| HARD-001 | `deterministic-foundations-hard-001-rerun-20260726` | valid / completed | `449b3adf8cfde8e5185173b72bdaa33ac935d7a0c76ba81d96f8f6363b24c211` | 18 | none attached |
| HARD-002 | `deterministic-foundations-hard-002-rerun-20260726` | valid / completed | `f6cf0f9c181196993783e543bc4e02833726f0066ca10bfac0669c6b7c88cf5b` | 18 | none attached |
| HARD-004 | `deterministic-foundations-hard-004-parallel-20260726` | valid / completed | `ed0b9fb0c6ca11736219294159f8805114406b40b1e913c91388513bc42a55e0` | 18 | none attached |
| HARD-005 | `deterministic-foundations-hard-005-parallel-20260726` | valid / completed | `f054fafd850fbbfb7300e9a90ec825783e51ca77317f83fd1b95095ca458abf2` | 18 | none attached |
| FOUND-GATE-01 | `deterministic-foundations-gate-parallel-20260726` | valid / completed | `df1a5ef6bcda99e880c3f3344fa0958ec836a1b556c519b55651e0b27187b295` | 18 | none attached |

## Results used for integration

- HARD-001: implementation criteria passed; remaining limitation is the deliberate interactive-only `tmux.attach` boundary and parent progress emission in the read-only host state.
- HARD-002: path/schema criteria passed; filesystem-socket coverage was unavailable on this host.
- HARD-005: metadata-only MCP, no-follow, bounded-error, and receipt-summary criteria passed; installed stdio MCP coverage was not verified.
- HARD-004: correctly stopped without changes because HARD-001/HARD-002 had no accepted phase disposition at launch.
- FOUND-GATE-01: rejected the foundation phase because shared installed-product acceptance, immutable authority, and accepted prerequisite evidence were not complete.
- HOOK-DOGFOOD-001: hook configuration and installer preservation criteria passed; full host release checks remained environment-limited.

## Eval and ledger result

No run supplied an evaluation plan (`evaluation_path: null` for all six). Therefore no score, report, or score-set collection exists. `agent-workflow eval collect` was attempted against the sealed runs and failed closed because `scores/score-set.json` is absent; this is recorded as unavailable evidence, not a score.

`agent-workflow ledger deterministic-enforcement-foundations` produced a zero-row ledger because these were implementation/review runs without attached evaluation plans. The exact output is retained in [`deterministic-foundation-ledger-20260726.tsv`](deterministic-foundation-ledger-20260726.tsv).

The independent phase gate remains rejected; the backlog uses `in-review` for integrated HARD-001/HARD-002/HARD-005 and keeps HARD-004 blocked pending a subsequent accepted shared gate.
