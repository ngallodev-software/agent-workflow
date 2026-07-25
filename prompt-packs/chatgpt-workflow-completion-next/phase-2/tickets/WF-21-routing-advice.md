# WF-21 — Deterministic routing advice

Implement a pure advisory function over existing task metadata that recommends current agent class, executor, model, and interactive mode with stable explanation codes. Existing configuration enforcement remains authoritative. Record recommendation, enforced selection, and policy disagreement separately. No embeddings, online learning, or config mutation. Test all rules and no-go rejection.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
