# HIER-001 — hierarchy and team-delegation contracts

## Objective

Add schema-validated immutable hierarchy and team delegation contracts that
express fixed depth, principal identity, scope, budgets, command/model policy,
message routes, dependencies, deliverables, stop conditions, and digests.

## Dependencies and lane

- External gate: maintainer approval of `DEC-005`.
- Critical path; first hierarchy implementation ticket.

## Required behavior

- Support only root, team-lead, and worker principals.
- A team lead can narrow but never widen delegated capabilities.
- Install contracts read-only before launch and bind their digests into run
  provenance.
- Validate IDs, paths, command catalog references, source identity, and bounded
  text/collections using existing fail-closed path patterns.
- Add invariant tests for scope/model/command/budget escalation attempts.
- Add strict future journeys for a two-team hierarchy.

## Non-targets

No tmux mutation, team scheduler, external terminal adapter, recursion, or
multi-host transport.

## Writable scope

Limit changes to the modules, schemas, focused tests, command/docs/man/skill surfaces directly required by this ticket. Preserve current direct-orchestrator compatibility and do not update `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant tests and an installed-product acceptance journey for the required behavior. Run package validation and relevant release audits. Record exact commands, exit codes, durable artifact paths, and receipt references.

## Acceptance criteria

All required behavior is proven from immutable contracts, append-only journals, verified receipts, and canonical service paths. Existing supported direct orchestration journeys remain green.

## Stop conditions

Stop and report rather than weakening durable authority, bypassing canonical launch/workflow services, inferring completion from tmux/process state, adding arbitrary recursion or multi-host infrastructure, widening permissions, or introducing shell-derived terminal commands.

## Feature-boundary steering

Implement hierarchy-specific contracts, services, state, and policy in the dedicated built-in hierarchy feature package. Core authority services may be consumed through narrow public interfaces; do not embed hierarchy-only branches throughout generic session, scheduler, CLI, workflow, or tmux modules. Preserve direct orchestration as the default path and require explicit hierarchy enablement.
