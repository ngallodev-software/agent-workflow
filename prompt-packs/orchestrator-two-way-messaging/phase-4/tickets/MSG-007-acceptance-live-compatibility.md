# MSG-007 — installed-product acceptance and live compatibility

**Backlog:** [`MSG-007`](../../../../docs/BACKLOG.md)  
**Priority:** P1 / High  
**Design:** [Acceptance strategy](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acceptance-strategy)

## Goal

Create a small, comprehensive acceptance suite proving the complete two-way messaging user journeys through an installed wheel and public executables, plus an opt-in live lane for real tmux and supported executor adapters.

## Dependencies

- `BKL-002`, `MSG-001`, `MSG-002`, `MSG-003`, `MSG-004`, and `MSG-005`.

## Required implementation

- Add default installed-product journeys using a deterministic protocol-compatible external executor fixture and real temporary filesystem/Git/process state.
- Cover completion fan-in, missed wake, duplicate wake, restart, cursor reconstruction, safe orchestrator notification, acknowledgement/action, interactive reuse, detached late steering, and conflicting duplicate identity.
- Keep tests black-box wherever possible. Invoke installed `agent-workflow` executables as subprocesses and assert durable user-visible evidence.
- Add an opt-in live marker/lane for real tmux behavior and every executor adapter claimed as supported.
- Measure no-wakeup delivery latency, concurrent-child drain behavior, process count, output bounds, and clean shutdown against `DEC-001` and configuration policy.
- Ensure live tests skip explicitly with a reason when prerequisites/credentials are absent; they must not silently pass through mocks.
- Document the supported compatibility matrix and exact release-gate expectations without claiming unrun environments.
- Remove or consolidate any newly redundant internal tests discovered while the acceptance journeys prove the same behavior more directly.

## Writable paths

- New acceptance and live test files, external fixtures, CI/release-check wiring, and testing/compatibility documentation.
- Do not modify core messaging behavior except a narrowly reproduced defect coordinated with `MSG-006`.

Run in parallel with `MSG-006` using separate test filenames and worktree.

## Required journeys

1. Child completion produces one inbox event and one linked orchestrator action.
2. The same journey succeeds with no wake signal.
3. Duplicate signals and supervisor restart do not duplicate delivery/action.
4. A missing orchestrator process is resumed or started with a fixed opaque event token.
5. Malicious child text never reaches pane input or command construction.
6. Reusable interactive agent follow-up requires correlated acknowledgement.
7. Detached executor late steering produces applied/rejected/unsupported evidence.
8. Missing/corrupt cursor reconstructs safely.
9. Conflicting duplicate source IDs fail closed.
10. Concurrent children are drained fairly within configured bounds.

## Live compatibility

- Real tmux `wait-for`, pane verification, and fixed notification injection.
- Real supported Codex adapter journey.
- Real supported Claude adapter journey.
- Supervisor restart while several real sessions complete.

Record exact versions, host characteristics, command lines after redaction, skips, and limitations.

## Non-targets

- Restoring broad unit/mock suites.
- Paid benchmark comparisons unrelated to messaging correctness.
- Claiming executor support based only on fixtures.

## Stop conditions

Stop when a public journey requires private helper imports, a live adapter cannot be exercised honestly, the default suite depends on paid credentials, or the suite becomes an implementation-shape snapshot rather than a user outcome.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include test inventory before/after, default/live results, timing/resource measurements, supported adapter matrix, and any removed redundant tests.
