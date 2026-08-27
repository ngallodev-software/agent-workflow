# Phase 4 Checkpoint 02 — Phase 5 external Worker contract slice

This cumulative changes-only overlay starts from the authoritative verified Phase 3 source and includes Checkpoint 01.

Phase 4 itself remains satisfied by the deterministic `delegate` facade landed during Phase 2. Work has moved to the repository-defined Phase 5 (`BIND-001` + `API-001`) because that is the next unfinished simplification boundary.

## Implemented in this slice

- Added a host-neutral external Worker binding authority for Agent Runs prepared with `worker_mode=external`.
- Added an append-only run-local binding journal and rebuildable public projection; no parallel lifecycle authority or external-binding database was introduced.
- Added idempotent bind/rebind/unbind semantics, generation tracking, and explicit host observation timestamps.
- Added full/debug CLI JSON surfaces for bind, inspect, observe, and unbind. These commands were deliberately **not** added to normal orchestrator/implementation/review command profiles.
- Kept external runtime and worker identity opaque and provider-neutral.
- Documented the public contract and the hard boundary that host observations cannot imply completion, review, acceptance, failure, or steering acknowledgement.

## Still remaining in Phase 5

- delivery-adapter contract: fetch pending durable messages and report delivery attempts without auto-acknowledgement;
- review and normalization of the remaining `API-001` JSON surfaces (compact Agent Run context/status, completion/evaluation/review summary, workflow, provenance, benchmark-on-demand);
- final Phase 5 backlog/plan reconciliation after those public contracts are stable.

Testing: deliberately not run per phase checkpoint policy.
