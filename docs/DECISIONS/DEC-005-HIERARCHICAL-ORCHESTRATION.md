# DEC-005 — Bounded hierarchical orchestration

- **Status:** proposed
- **Date:** 2026-07-30
- **Decision owner:** maintainer
- **Related:** `DEC-001-DURABLE-CONTROL.md`, `HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md`

## Context

The current product can orchestrate direct agent sessions and durable workflows, but a large effort needs multiple independently supervised teams. Placing every worker pane and every decision under one root orchestrator creates attention, layout, capacity, and context bottlenecks.

## Decision

Introduce exactly three authority tiers: root orchestrator, team lead, and worker. The root creates one managed tmux session and one dedicated window per team lead. A team lead is a normal canonical session with a bounded delegation contract and may create worker runs/panes only inside its assigned team scope.

Durable hierarchy records, delegation contracts, inbox/action/acknowledgement journals, workflow events, and receipts are authoritative. tmux sessions/windows/panes and external terminal windows are local projections and wake/interaction mechanisms.

Version 1 does not support arbitrary recursive team creation or multi-host execution.

## Consequences

### Positive

- Root context and visual load are partitioned by team.
- Teams may progress concurrently while preserving one global dependency graph.
- Restart, replay, and audit semantics extend naturally from existing durable-control principles.
- The same protocol can later use a remote transport without changing authority.

### Negative

- Adds contracts, receipts, scheduling leases, and two message boundaries.
- Requires careful duplicate-launch prevention and tmux topology reconciliation.
- Team-lead prompts and command permissions become a security-sensitive surface.

## Rejected alternatives

1. **All workers in one root window:** simplest, but does not solve coordination/context scaling.
2. **Nested tmux sessions per team:** possible, but attachment and identity are more confusing than one root session with team windows; retain only as an optional future topology.
3. **Team leads as untracked interactive shells:** no durable identity, authority, or restart guarantees.
4. **Arbitrary recursive orchestrators:** excessive complexity and runaway-risk before a bounded hierarchy is proven.
5. **Redis/NATS-based hierarchy now:** operational burden without a current multi-host requirement.
