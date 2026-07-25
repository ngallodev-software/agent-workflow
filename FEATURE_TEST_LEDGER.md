# Feature and test ledger

**Release:** 0.2.1
**Updated:** 2026-07-24
**Purpose:** Current evidence map for behavior that materially affects orchestration authority, restart safety, provider accounting, and the planned MCP mutation surface.

This ledger is a release aid, not a substitute for immutable run/workflow receipts. A feature is marked `pass` only when its contract has focused executable coverage and the related documentation matches the implementation.

| Feature or boundary | Status | Evidence and protected failure |
|---|---|---|
| Durable message journal and tmux wake hint | pass | `tests/test_messages.py` and `tests/test_tmux.py` prove replay-first authority, fsynced append behavior, bounded waits, and fallback when tmux wakeups are lost or unavailable. |
| Workflow contract and replay | pass | `tests/test_workflow.py` validates schemas, contiguous event sequencing, legal transitions, snapshot identity, descriptor-safe immutable reads, lock/journal symlink rejection, restart reconstruction, active-capacity accounting, authoritative child reconciliation, retry lineage, projection recovery, and dependency-failure reopening. |
| Receipt-backed approval gates | pass | `tests/test_approval.py` reconstructs the canonical append-only lifecycle chain, ignores mutable status projections, rejects symlinked receipt roots, lock files, non-regular or writable receipts, and fails closed on copied, omitted, duplicated, or tampered evidence. |
| Bounded result binding | pass | `tests/test_bindings.py` validates the supported RFC 6901 subset, ancestry, result/collection digests, per-value and aggregate size limits, optional/missing behavior, immutable parent snapshots, read-only child launch copies, and byte-stable replay. |
| Aggregate workflow receipts | pass | `tests/test_workflow_receipt.py` binds the normalized snapshot, durable event stream, exact node terminal states, retry attempts, child seals, bindings, and canonical approval evidence. Substitution, omission, duplication, partial state, post-seal approval tampering, and receipt/artifact symlink redirection fail verification. |
| Authorized workflow templates | pass | `tests/test_workflow_templates.py` covers only pipeline, bounded parallel-review/fan-in, and implementation-independent-review expansion and checks deterministic output. |
| Deterministic routing advice | pass | `tests/test_routing.py` verifies stable explanation codes, recommendation/enforcement separation, disagreement reporting, and fail-closed no-go policy. Launch still passes through the canonical session/config policy. |
| Provider stream evidence | pass | `tests/test_provider_evidence.py` covers bounded stable raw-stream capture, symlink/change rejection, event digests/sequences, identified replay idempotency with conflicting-ID rejection, ambiguous unidentified deltas, explicit delta/cumulative/terminal modes, monotonic totals, finite nonnegative usage, cached/cache-write/reasoning fields, terminal conflict rejection, complete currency/catalog metadata, and provider-billed versus catalog-estimated cost separation. |
| Trial collection and comparison | pass | `tests/test_eval_trials.py`, `tests/test_eval_compare.py`, and evaluation command tests reject incomplete/unsealed evidence and forged mutable score sets, validate regular read-only content-addressed scorer receipts against the exact verified final-seal digest, preserve nulls, bind source digests, and exclude currency/catalog mismatches from cost comparisons. |
| Sealed artifact path integrity | pass | `tests/test_receipts.py` covers stable final-receipt reads, exact artifact digests, optional-tree immutability, descriptor-based chmod, final/intermediate symlink rejection, and outside-target protection. |
| Retry accounting | pass | `tests/test_metrics.py` proves retry count is derived from sealed provenance or workflow attempt lineage rather than mutable session status. |
| Read-only MCP adapter | pass | `tests/test_mcp_services.py` and `tests/test_mcp_server.py` cover bounded resource access, configured-root containment, traversal/symlink rejection, redaction, protocol initialization, and the existing read-only/validation capability surface. |
| MCP mutation tools | not implemented | `MCP-003` is ready now that `WF-22` is complete. The proposal and threat model require reuse of canonical services, idempotency, durable result identifiers, and no raw shell/tmux/path authority. |
| Real-executor benchmark cohort | not run | `BKL-004` remains a controlled external execution task. No provider/model winner or production routing recommendation is claimed from synthetic fixtures. |
| Fresh independent external-agent review | unavailable in this environment | Historical independent reviews accepted WF-00 through WF-02 and rejected the original WF-10 status-path trust flaw. The corrected cumulative tree has focused tamper tests and a local critical review; no new Codex/Claude executable was available, so no external receipt is fabricated. |

## Release-gate commands

The final command results for this delivery are recorded in `docs/execution-evidence/WORKFLOW_BENCHMARK_PHASE_GATE.md` and `docs/execution-evidence/FINAL_CRITICAL_REVIEW.md`. The release manifest must be regenerated after every source, documentation, schema, skill, prompt-pack, or test change.

## Interpretation rules

- Terminal capture is observational and never proves lifecycle state, usage, approval, or message delivery.
- `status.json` is a projection; canonical append-only records and sealed artifacts are authoritative.
- Unknown tokens, cost, currency, retry details, or durations remain `null`; they are not inferred from prose.
- A best-effort tmux wakeup may be lost, duplicated, or unavailable without losing a durable message.
- MCP is an adapter over repository services. It must not become a parallel workflow engine or expose arbitrary shell, filesystem, environment, or tmux control.
