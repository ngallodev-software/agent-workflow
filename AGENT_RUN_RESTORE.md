# Agent Run Restore

Restore work from source, immutable Agent Run contracts, append-only journals, sealed evidence, and workflow snapshots.

Do not depend on a prior interactive host, mutable status projection, local UI state, or host-specific absolute paths.

Recommended sequence:

1. restore/verify the repository source;
2. install the current package and dependencies;
3. run `agent-workflow doctor`;
4. verify the relevant worktree/source baseline;
5. inspect Agent Run contracts and durable journals;
6. rebuild mutable status/index projections where needed;
7. resume workflow scheduling or create a new Agent Run with retry lineage;
8. rerun applicable tests/evaluations before acceptance.
