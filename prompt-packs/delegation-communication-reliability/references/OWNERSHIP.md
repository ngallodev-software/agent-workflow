# Ownership and boundaries

This pack owns only `PROC-001` through `PROC-005`. It does not own BKL-001 or
BKL-002, MSG-001 through MSG-007, HARD-004 implementation itself, MCP-003, or
actor authentication. Those existing tickets remain authoritative for their
runtime scope. A proposed change that crosses one of those boundaries must
stop and escalate rather than silently claim ownership.
