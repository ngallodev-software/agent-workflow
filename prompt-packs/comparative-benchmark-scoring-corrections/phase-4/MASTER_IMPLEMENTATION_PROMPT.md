# Phase 4 master implementation prompt

Implement the phase-4 manifest in dependency order against agent-workflow 0.7.9. Treat the operator experience as part of benchmark correctness, not presentation polish.

Required invariants:

- `benchmark run` is invoked inside tmux and creates exactly two additional panes in the invoking window, one per arm;
- the two stable pane IDs are reused across phases, retries, and final review display;
- model/provider stdout and stderr are streamed visibly while bounded durable evidence is written;
- cancellation or pane replacement terminates the complete provider process group;
- each selected arm worktree is served by an independently supervised live application after automated scoring;
- status and blinded assignments expose current review URLs without treatment leakage;
- normal completion and default cleanup preserve live applications and worktrees;
- explicit stop/removal is safe, idempotent, and provenance-preserving;
- the compact benchmark has one model phase with a hard timeout below 180 seconds and retains the same paired experimental and review lifecycle;
- authoring and packaged benchmark suites are exact byte-for-byte mirrors.

Use the tickets for writable scope, tests, and stop conditions. Do not recreate detached per-arm tmux sessions, hide provider output in log files only, substitute static screenshots for a live review app, or weaken the corrected score to make the fast suite easier.
