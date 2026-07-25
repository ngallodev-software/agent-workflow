# ChatGPT Workflow Foundations and Benchmark Completion

> Status: executed against release 0.2.0; retained as the authoritative implementation input and reproducibility pack.

This pack is the ordered implementation handoff for ChatGPT. It completes
WF-10, WF-11, WF-12, WF-20, WF-21, WF-22, and BKL-003, including the research
needed to make BKL-003 safe and evidence-backed. Work must continue through
all tickets and the final critical review/fix pass; do not stop after a merely
green local test run.

The current source checkout and companion source archive are authoritative
when they differ. `BACKLOG.md` remains the canonical task register.

## Required execution order

1. Verify WF-00/WF-01/WF-02 and existing MCP/read-only foundations.
2. Complete WF-10 → WF-11 → WF-12.
3. Complete WF-20 → WF-21 → WF-22.
4. Complete BKL-003-RESEARCH, then BKL-003 implementation and evidence gates.
5. Run the mandatory critical review across every changed ticket, fix errors,
   drift, stale documentation, manifest defects, security issues, and
   regressions, then rerun all gates.

Every ticket requires an isolated worktree, durable completion evidence,
focused tests, relevant full-suite tests, release-audit validation, and an
independent review before integration. Preserve the existing launch service
as the only execution authority. Do not implement MCP mutation tools unless a
ticket explicitly permits them.

## Research requirements

Use the supplied research references first, then verify unstable or provider-
specific facts against primary official documentation. Record URLs, access
dates, assumptions, exclusions, and unresolved questions in repository
research/evidence documents. BKL-003 must not infer usage or cost from prose,
terminal capture, or incomplete provider output.

## Operational boundary

Run `agent-workflow pack validate` before execution. Create each worktree with
`agent-workflow worktree create` and launch each bounded ticket with
`agent-workflow launch`. A valid current tmux context creates a visible pane;
an unusable context falls back to a detached named session. Native host
subagents are not durable workflow runs unless explicitly bridged through the
CLI. Claude agents are interactive by default; use `--no-interactive` or
`--structured` only when the ticket explicitly requires detached execution.
