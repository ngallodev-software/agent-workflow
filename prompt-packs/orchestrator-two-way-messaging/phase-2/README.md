# Phase 2 — safe wake and restart reconstruction

    ## Purpose

    Run orchestrator wake/resume adapters and restart reconstruction concurrently after the supervisor contract stabilizes.

    ## Tickets

    - `MSG-003`
- `MSG-005`

    ## Execution

    Respect every manifest dependency and every external prerequisite named in the ticket. Dependency-free tickets in this phase may run concurrently only in separate worktrees and sessions. Integrate reviewed diffs deliberately, rerun shared installed-product journeys, and run the release drift audit before advancing.
