---
schema: agent-workflow/phase-gate/v1
pack_id: ""
phase: ""
review_session: ""
decision: "accepted|rejected|accepted_with_follow_up"
---

# Phase Gate Report

## Ticket status

| Ticket | Branch/commit | Review result | Notes |
|---|---|---|---|

## Independent gate commands

| Command | Exit code | Result summary |
|---|---:|---|

## Boundary audit

- [ ] Authority and ownership boundaries remain intact.
- [ ] No unexpected data migration or secret exposure occurred.
- [ ] No unsupported flags, paths, or compatibility claims remain in phase scope.
- [ ] Tests correspond to real contracts or failures.
- [ ] Documentation and skills do not claim unimplemented behavior.
- [ ] Changed files stayed inside ticket writable scopes.

## Rejected or deferred work

## Decision rationale
