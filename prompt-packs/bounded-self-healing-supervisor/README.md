# bounded-self-healing-supervisor

Complete the bounded, deterministic supervision architecture in
`docs/SELF_HEALING_SUPERVISOR_ARCHITECTURE.md`. The current implementation
already separates supervisor liveness from semantic progress, records bounded
health/terminal/permission/incident/remediation evidence, repairs reconstructable
status projections, and offers a foregroundable supervisor with safe defaults.
This pack closes the security, enforcement, live-compatibility, hierarchy, and
performance gates without allowing an agent to expand its own authority.

## Execution gates

- `DEC-006` is decided and governs every ticket.
- `HARD-006` must be accepted before `SUP-003` can close.
- `HARD-003` must be accepted before `SUP-004` can close.
- `HARD-007` must be accepted before `SUP-005` can close.
- `REL-003` and Phase 1 acceptance are required before `SUP-006`.
- `HIER-005` and `HIER-006` are required before `SUP-007`.
- `BKL-004`, `HIER-007`, and `SUP-006` are required before `SUP-008`.
- Manifest `dependencies` are authoritative for in-pack ordering.

Critical path:

```text
SUP-001 → SUP-002 → SUP-GATE-0
                    ↓
      SUP-003 + SUP-004 + SUP-005 → SUP-GATE-1
                    ↓
                SUP-006 → SUP-GATE-2
                    ↓
                SUP-007 → SUP-008 → SUP-GATE-3
```

`SUP-003`, `SUP-004`, and `SUP-005` may execute in parallel after their external
hardening prerequisites are accepted.
