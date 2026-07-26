# Future acceptance journeys

These tests specify approved backlog outcomes that are intentionally absent. Every test is marked `future` and `xfail(strict=True)` so an unexpected pass forces review rather than silently claiming completion.

Current coverage:

- `BKL-002`: detached late steering and correlated acknowledgement;
- `HARD-004`: immutable launch and final-receipt authority;
- `MSG-005`: durable restart replay without duplicate semantic effects;
- `BKL-004`: complete, comparable evaluation cohorts and truthful ledger state;
- `MCP-003` / `HARD-007`: authenticated mutation with preserved read-only MCP boundaries.

Run only these specifications with `pytest -q tests/future`. A backlog item may lose its `xfail` only after implementation, installed-product acceptance evidence, and the owning phase gate are accepted.
