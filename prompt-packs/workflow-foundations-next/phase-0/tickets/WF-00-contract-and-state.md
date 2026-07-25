# WF-00 — Workflow contract and durable state

Define the minimal workflow-run schema, immutable pack snapshot, node/run binding, append-only event envelope, and reconstructable status projection. Writable: workflow schemas, workflow domain module, tests, directly related docs. Acceptance: unknown/cyclic graphs remain rejected; status can be rebuilt solely from snapshot plus events; no mutable store becomes authoritative. Test all transitions and corruption handling. Stop if implementation requires arbitrary workflow code or a second executor path.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
