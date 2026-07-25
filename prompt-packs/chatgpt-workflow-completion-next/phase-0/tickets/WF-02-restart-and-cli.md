# WF-02 — Restart recovery and CLI

Add minimal `workflow validate`, `workflow start`, `workflow status`, and `workflow resume` commands over the scheduler service. Writable: CLI, workflow service, tests, docs. Acceptance: JSON output is stable and bounded; resume reconstructs state before scheduling; CLI and future MCP adapters share the same service; no HTTP or daemon is added. Test restart, duplicate invocation, invalid roots, and terminal workflows.


## Execution constraints

Writable paths are limited to the files named by this ticket and directly related tests and documentation. Acceptance requires focused tests plus the relevant full-suite slice. Stop if current source contradicts the ticket or the change would introduce a listed non-target.
