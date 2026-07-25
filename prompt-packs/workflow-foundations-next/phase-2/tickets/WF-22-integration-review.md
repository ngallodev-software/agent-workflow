# WF-22 — Critical integration review

Review scheduler, gates, binding, templates, and routing against current tmux, interactive session, naming, model policy, MCP, receipts, and global routing contracts. Remove speculative abstractions and stale docs. Run the full suite and release audit. Acceptance: no alternate launch path, no hidden mutable authority, no external-project terminology, and all backlog states/evidence are current.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
