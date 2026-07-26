# CHATGPT-TDD-001 — future planned-work TDD journeys

Backlog: `CHATGPT-TDD-001`  
Dependency: accepted `CHATGPT-EVAL-001`  
Writable scope: `tests/future/`, future-test documentation, and this ticket's evidence notes.  
Non-targets: runtime implementation of HARD-003/004/006/007/008, BKL-001/002, MSG-001..007, or MCP-003.

## Acceptance

- Generate installed-product TDD journeys for the planned work's user-visible outcomes, not private helper shapes.
- Tie each journey to an existing future backlog ID and use `pytest.mark.future` with `xfail(strict=True)` where implementation is intentionally absent.
- Cover at least immutable launch/receipt authority, durable messaging/restart semantics, evaluator score/ledger completeness, and MCP read authorization boundaries where those are planned and not yet accepted.
- Assert the desired failure/acceptance contract strongly enough that an implementation cannot pass by weakening the test.
- Run the future-test collection and relevant release gates; report expected failures separately from unexpected failures.

Stop after the future TDD journeys, collection evidence, and completion report are sealed; do not implement the planned runtime features.
