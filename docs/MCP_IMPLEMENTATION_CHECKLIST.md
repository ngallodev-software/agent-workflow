# MCP implementation checklist

## MCP-003 safe mutation gate

- [ ] Define versioned request/result/event schemas.
- [ ] Add append-only fsynced request journal and replay projection.
- [ ] Reserve idempotency keys before external effects.
- [ ] Reconcile accepted-but-nonterminal operations after restart.
- [ ] Extract only the minimum CLI logic needed into shared services.
- [ ] Add `worktree_create` without arbitrary paths.
- [ ] Add `run_launch` through canonical session launch and policy selection.
- [ ] Add workflow validate/start/status/resume/seal/verify through `WorkflowService`.
- [ ] Add progress/ack/steer through durable message APIs.
- [ ] Preserve `pending` steering semantics.
- [ ] Add request resource with bounded status/result evidence.
- [ ] Add CLI/MCP equivalence tests.
- [ ] Add traversal, symlink, redaction, bounds, conflict, crash, and replay tests.
- [ ] Run MCP Inspector and publish capability matrix.
- [ ] Update README, command reference, man page, skills, backlog, changelog, and release manifest.

## MCP-004 destructive/review gate

- [ ] Obtain explicit authorization after MCP-003 evidence review.
- [ ] Add per-action feature flags.
- [ ] Add interrupt/terminate only; keep force kill excluded unless separately approved.
- [ ] Add review/accept/reject through lifecycle service.
- [ ] Require actor, reason, exact revision, score/final-receipt validity, and reviewer independence.
- [ ] Add duplicate-transition and stale/forged evidence tests.
- [ ] Repeat Inspector, host, security, full-suite, and release gates.

## MCP-005 HTTP decision gate

- [ ] Record actual adoption/multi-process need.
- [ ] Write authorization/deployment ADR.
- [ ] Decide tenant model, IdP, resource/audience validation, registration, Origin, TLS, proxies, session persistence, rate limits, and audit retention.
- [ ] Approve or reject implementation before code exists.
