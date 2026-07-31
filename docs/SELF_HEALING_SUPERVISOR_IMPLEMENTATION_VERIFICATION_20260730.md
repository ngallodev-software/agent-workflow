# Self-Healing Supervisor Implementation Verification

**Date:** 2026-07-30  
**Baseline:** `agent-workflow 0.3.0-e9e5b95` plus the cumulative hierarchical/backlog-blocker v3 overlay  
**Decision:** [`DEC-006 — Bounded deterministic self-healing`](DECISIONS/DEC-006-BOUNDED-SELF-HEALING.md)

## Scope delivered

This change set implements the observable foundation and foreground supervisor represented by `SUP-001` and `SUP-002` in the canonical backlog.

### Runtime evidence

- `run-health-samples.jsonl` separates runner liveness, executor liveness, host/process resources, and semantic progress.
- `terminal-events.jsonl` records bounded, change-driven, ANSI-cleaned, secret-redacted interactive pane snapshots.
- `permission-events.jsonl` records observed pending, denied, and cleared permission states without granting authority.
- `incident-events.jsonl` records typed, fingerprint-deduplicated unattended diagnoses.
- `remediation-events.jsonl` records versioned rule, attempt, action, outcome, and bounded verification details.
- `process-result.json` records process identity, return/exit/signal state, timeout/cancellation, byte totals, truncation, and environment policy.
- Every new journal record and process-result document is validated against a packaged JSON Schema before persistence and when replayed.

### Supervisor behavior

`agent-workflow supervisor once` and `agent-workflow supervisor run` provide a foregroundable deterministic reconciliation loop. The implemented rules are:

| Rule | Default | Result |
|---|---:|---|
| `SAFE-REPAIR-STATUS-v1` | enabled | Reconstruct corrupt or missing mutable status from immutable launch/lifecycle/sealed evidence. |
| `SAFE-PROBE-STALL-v1` | enabled | Send one durable progress probe when a live executor has no semantic progress beyond the configured threshold. |
| `OPT-IN-INTERRUPT-STALL-v1` | disabled | Interrupt a stalled executor only when an operator explicitly authorizes the rule. |
| `OPT-IN-RESTART-ORPHAN-v1` | disabled | Create a lineage-preserving retry only when an operator explicitly authorizes the rule. |

Permission prompts are evidence and escalation conditions. The supervisor never answers them, widens scope, changes budgets, accepts work, merges, or deletes evidence.

### Presentation and documentation

- README replaced with a current-state, professional project entry point.
- Responsive light/dark SVG hero and architecture graphics added.
- Social-preview graphic added.
- Detailed architecture, decision, operations, security, testing, command, changelog, release-audit, and backlog documentation updated.
- Four Mermaid sources describe topology, lifecycle, evidence relationships, and state transitions.
- A four-phase, twelve-task prompt pack owns all work not safely completed in this pass.

## Verification performed

### Source-level invariant, release, future-specification, and preflight slice

```text
103 passed, 10 xfailed
```

The ten expected failures are strict future specifications for genuinely open work, including governed telemetry retention, resource enforcement, authenticated principals, live recovery compatibility, hierarchical supervision, and performance control.

### Focused installed-product and invariant supervisor slice

```text
8 passed
```

Installed-product journeys prove that the built wheel:

1. detects a live-but-stalled run and sends exactly one durable, idempotent progress probe;
2. surfaces a permission wait without granting it or recording a fake principal;
3. repairs a corrupt mutable status projection from immutable evidence.

Invariant tests additionally prove terminal capture change detection and redaction, semantic-progress separation, schema replay/tamper rejection, and preservation of signal/truncation process facts.

### Structural validation

- Python compilation: passed.
- Release-asset audit: passed.
- Every active prompt pack validates as an acyclic cross-phase dependency graph.
- New self-healing prompt pack: `4 phases`, `12 tasks`, `valid: True`.
- SVG assets rendered successfully using non-browser tooling; the graphics avoid fragile filter effects.

## Environment limitations

The configured package mirror does not provide the project-pinned `mcp==1.28.1` dependency. Non-MCP installed-product checks were run using a temporary local distribution-metadata stub so the wheel-install fixture could exercise the core CLI. No MCP protocol behavior was simulated or claimed.

The container does not provide a real supported tmux/executor compatibility matrix. Live tmux pane-loss, missed-wakeup, executor-specific permission prompts, resource exhaustion, and restart behavior remain explicitly gated by `SUP-006` and `REL-003` rather than being represented as complete.

## Remaining sequenced work

The canonical order is:

```text
SUP-001 → SUP-002 → SUP-GATE-0
                      ├─ [HARD-006] → SUP-003 ─┐
                      ├─ [HARD-003] → SUP-004 ─┼→ SUP-GATE-1
                      └─ [HARD-007] → SUP-005 ─┘
                                                ↓
                               [REL-003] → SUP-006 → SUP-GATE-2
                                                ↓
                     [HIER-005 + HIER-006] → SUP-007
                                                ↓
                     [BKL-004 + HIER-007] → SUP-008 → SUP-GATE-3
```

See [`BACKLOG.md`](BACKLOG.md) and [`SELF_HEALING_SUPERVISOR_ARCHITECTURE.md`](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md) for exit evidence and authority boundaries.

## Overlay application verification

The cumulative overlay contains 133 exact repository payload paths. Its apply path was verified against:

1. the untouched `0.3.0-e9e5b95` source archive;
2. a tree with the cumulative v3 hierarchy/backlog-blocker overlay already applied;
3. repeated v4 application to prove idempotence.

For each target, every payload byte matched the overlay and both superseded paths were absent after application. The applied-source tree then repeated compilation, the 103-pass source validation slice, release-asset audit, all prompt-pack validations, and the eight focused supervisor tests successfully. The archive was extracted independently and its complete SHA-256 transfer manifest was verified.
