# WF-12 — Aggregate workflow receipt

Seal a terminal workflow receipt containing the workflow snapshot digest, event-log digest, node IDs, bound run IDs, child final-receipt digests, approval receipt digests, and terminal outcome. Provide verification. Test substitution, omission, duplicate nodes, and partial workflows.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
