# GIT-LEASE-001 implementation

Headless workers may edit linked worktrees while their Git object/index storage
is mounted read-only by the execution sandbox. A launch must not claim writable
Git authority merely because a path was supplied with `--add-dir`.

Implement a fail-closed preflight that proves the worker can create and remove
a temporary file in the resolved Git administrative directory before launch.
If unavailable, reject before mutable Agent Run state with an actionable
coordinator-commit instruction. Completion validation must also reject a
declared head revision that is absent from the recorded repository object
database. Preserve existing sealed evidence and never synthesize commits in a
private alternate object store.

Prove writable and read-only cases, missing completion objects, and ordinary
non-Git delegation behavior.
