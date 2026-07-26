# Phase 1 — supervisor and late delivery

    ## Purpose

    Run the aggregate supervisor and executor-specific late-steering adapter work concurrently after phase 0.

    ## Tickets

    - `MSG-002`
- `BKL-002`

    ## Execution

    Respect every manifest dependency and every external prerequisite named in the ticket. Dependency-free tickets in this phase may run concurrently only in separate worktrees and sessions. Integrate reviewed diffs deliberately, rerun shared installed-product journeys, and run the release drift audit before advancing.
