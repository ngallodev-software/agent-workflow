# Security trust boundaries

## Boundary map

1. **Operator/config input:** trusted intent but validated types, IDs, policy, and paths.
2. **Prompt-pack content:** project-controlled and potentially adversarial; constrained by pack roots, manifests, schemas, checksums, and writable scopes.
3. **Target repository/worktree:** untrusted code executed only through declared commands/executors; isolated per ticket.
4. **Executor process:** external binary with versioned provenance; stdout/stderr are untrusted bounded evidence.
5. **Durable state:** local filesystem authority; atomic JSON, fsynced JSONL, regular-file/symlink checks, and read-only receipts detect substitution.
6. **Reviewer:** separate lifecycle authority; acceptance requires canonical evidence and exact revision.
7. **MCP client:** local stdio principal plus untrusted tool content; current surface is bounded/read-only. Network identity is not yet authorized.

## Authority matrix

| Question | Authoritative evidence | Not authoritative |
|---|---|---|
| Did a run execute/finish? | lifecycle events, final status, final receipt | tmux pane text alone |
| Did a child apply a steer? | correlated acknowledgement/application record | steer write, wait-for signal, prose claim |
| Is a run reviewable/approved? | sealed `final-status.json`, canonical final receipt, and canonical lifecycle receipt chain | mutable `status.json` state, tier, executor, digest, or receipt pointer |
| What workflow state exists? | normalized snapshot + contiguous workflow event journal | workflow status projection alone |
| What result value may a child consume? | sealed ancestor `result.json` + binding snapshot | arbitrary files or live source reads |
| What tokens/cost count? | bounded raw provider events + explicit normalization mode | logs, model estimates without catalog |
| Is a release complete? | tests, release audit, manifest, checksums | version string or hand-written report alone |

## Required controls

- reject traversal, symlink escapes, unsafe IDs, unknown schema fields, and over-limit data;
- reserve append-only records before projections or external-effect claims;
- preserve prior runs and retry lineage;
- keep provider billed versus estimated cost distinct;
- require exact workflow snapshot matching after start;
- derive lifecycle-review authority from sealed terminal evidence and verify canonical final/lifecycle/workflow receipts as regular non-symlink read-only files;
- never infer approval, delivery, cost, or completion from terminal output;
- avoid vendored third-party source unless it is an intentional maintained dependency boundary.
