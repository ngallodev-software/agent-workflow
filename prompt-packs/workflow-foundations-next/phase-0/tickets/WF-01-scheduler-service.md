# WF-01 — Dependency scheduler service

Implement eligibility calculation, bounded parallel launch planning, dependency failure propagation, and retry lineage. Invoke the existing launch domain service; do not shell out to the CLI or spawn executors directly. Writable: workflow service, narrow launch seam refactor if required, tests, docs. Acceptance: each eligible node launches at most once per binding; restart replay is idempotent; parallelism is bounded; failed prerequisites block dependents. Stop on policy ambiguity.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
