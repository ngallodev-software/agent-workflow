# Future acceptance journeys

These tests specify approved backlog outcomes that are intentionally absent. Every test is marked `future` and `xfail(strict=True)` so an unexpected pass forces review rather than silently claiming completion.

Current coverage:

- `HARD-004`: immutable launch and final-receipt authority;
- `BKL-004`: complete, comparable evaluation cohorts and truthful ledger state;
- `MCP-003` / `HARD-007`: authenticated mutation with preserved read-only MCP boundaries.

Run only these specifications with `pytest -q tests/future`. A backlog item moves out of this directory after implementation and installed-product evidence exist; canonical backlog state may remain `in-review` until its owning phase gate and external prerequisites are accepted.
