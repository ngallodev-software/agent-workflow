# Future acceptance journeys

These tests specify approved backlog outcomes that are intentionally absent. Every test is marked `future` and `xfail(strict=True)` so an unexpected pass forces review rather than silently claiming completion.

Current coverage:

- `MSG-005`: restart reconstruction and oversized/inconsistent projection recovery;
- `BKL-004`: complete, comparable evaluation cohorts and truthful ledger state;
- `MCP-003` / `HARD-007`: authenticated mutation with preserved read-only MCP boundaries.

Graduated coverage:

- `HARD-004` is implemented and covered by installed/invariant status-tamper and immutable-receipt journeys, so its planning placeholder was removed.

Run only these specifications with `pytest -q tests/future`. A backlog item moves out of this directory after implementation and installed-product evidence exist; canonical backlog state may remain `in-review` until its owning phase gate and external prerequisites are accepted.
