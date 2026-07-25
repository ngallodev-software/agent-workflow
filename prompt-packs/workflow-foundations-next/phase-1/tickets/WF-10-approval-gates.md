# WF-10 — Receipt-backed approval gates

Add an approval node satisfied only by a valid review/lifecycle receipt referencing the expected child final-receipt digest. No mutable approval boolean is authoritative. Acceptance: accepted and rejected paths are distinct, tampered or unrelated receipts fail closed, and downstream eligibility follows durable evidence. Update tests and docs.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
