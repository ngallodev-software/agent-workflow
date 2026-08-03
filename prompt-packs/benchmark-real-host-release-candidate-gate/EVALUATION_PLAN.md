# Detailed completion evaluation plan

## Decision model

The evaluation has two simultaneous outputs:

1. a weighted diagnostic score totaling 100 points;
2. mandatory hard gates.

All checks are mandatory. The weighted score helps identify where a candidate failed; it is not a compensation mechanism. Acceptance requires exactly 100 points, every check in `pass`, no unresolved critical/high defect, and an independent final decision of `accept`.

## Evaluation domains

| Domain | Points | Purpose |
|---|---:|---|
| Local and package integrity | 15 | Prove the transferred source, tests, package mirrors, and release checks are trustworthy |
| Host readiness and authentication | 10 | Prove the host can execute the intended subscription-backed tmux/browser workflow |
| Real Codex fast run | 20 | Prove same-window panes, visible streams, timing, usage, and preserved runtime with Codex |
| Real Claude fast run | 15 | Prove the same properties independently with Claude |
| Full-suite and process safety | 12 | Prove multi-phase pane reuse, cancellation, and fresh-pair retry isolation |
| Live browser, scoring, and human review | 15 | Prove preserved apps, deterministic visual evidence, blinding, human scoring, and verification |
| Lifecycle and cleanup | 5 | Prove restart, preservation-first cleanup, and safe destructive teardown |
| Documentation, evidence, and independent gate | 8 | Prove the handoff is auditable, synchronized, and independently accepted |
| **Total** | **100** | |

## Required evidence classes

- source/archive checksums and inventory;
- installed package version/location and exported-suite digests;
- command transcripts with exit codes;
- tmux snapshots before launch, during execution, after automated completion, and after cleanup;
- pane-monitor summaries and timestamped captures;
- process-tree snapshots for cancellation;
- benchmark run plan, run state, events, metrics, scores, consolidation receipt, report, and manifest;
- live-review runtime summary and HTTP probes;
- browser screenshots, DOM/accessibility/download evidence, and console logs;
- blinded assignment/template, submitted review, and post-submission mapping-integrity check;
- cleanup results and post-cleanup verification;
- independent gate report.

## Real-provider run matrix

| Run | Suite | Executor | Policy | Repetitions | Purpose |
|---|---|---|---|---:|---|
| `codex-fast-rc` | `priority-picker-fast-v1` | `codex-subscription.json` | development | 1 | Codex pane/stream/timing/live-review gate |
| `claude-fast-rc` | `priority-picker-fast-v1` | `claude-subscription.json` | development | 1 | Claude pane/stream/timing/live-review gate |
| `full-v2-rc` | `priority-picker-v2` | authenticated subscription profile | development | 1 | Three-phase stable-pane gate |
| `cancel-rc` | `priority-picker-fast-v1` | authenticated subscription profile | development | 1 | Process-group cancellation and retry gate |

Run IDs may be suffixed with date/time but must remain unique and be recorded in `eval-results.json`.

## Pass/fail rules

- A command with nonzero exit is a fail unless the check explicitly expects that failure and records the expected classification.
- Missing evidence is `not_run`, not pass.
- Provider outage/auth unavailability is `blocked`, not fail, but still prevents acceptance.
- Host misconfiguration is `blocked` until corrected; it cannot be waived.
- An implementation defect is fail until repaired and rerun from a new run ID.
- A manual observation must name the observer and UTC interval and reference supporting pane/browser captures.
- A final reviewer cannot accept a check solely from the implementer's prose.

## Independent gate

The final reviewer reruns the smallest deterministic subset, samples raw evidence from every domain, verifies hashes, inspects the complete diff, and records one decision:

- `accept`: all mandatory checks pass and evidence supports the claims;
- `reject`: one or more required behaviors fail;
- `blocked`: execution is incomplete because a named external prerequisite is unavailable.
