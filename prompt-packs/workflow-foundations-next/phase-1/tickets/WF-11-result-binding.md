# WF-11 — Structured result binding

Allow declared downstream inputs to select fields from validated predecessor `result.json` using JSON Pointer. Snapshot resolved values and source digests into child provenance. Enforce size limits and fail closed on missing required fields. Do not add an expression or template language. Test malformed pointers, oversized values, absent results, and retry lineage.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
