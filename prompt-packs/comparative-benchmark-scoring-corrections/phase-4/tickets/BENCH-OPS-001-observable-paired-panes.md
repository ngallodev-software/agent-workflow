# BENCH-OPS-001 — Run paired arms in two observable panes

**Backlog:** `BENCH-OPS-001`  
**Priority:** P0 / Critical  
**Dependencies:** BENCH-CORR-001  
**Baseline:** `agent-workflow` 0.7.9

## Objective

Replace detached benchmark sessions with exactly two stable arm panes created in the tmux window that launched the benchmark. Stream provider progress and output to those panes while retaining bounded machine-readable evidence.

## Writable scope

`src/agent_workflow/benchmarking/operator_panes.py`, `runner.py`, `tmux_runner.py`, focused benchmark schemas/tests, and directly related help/docs. Keep generic tmux behavior behind the existing shared `agent_workflow.tmux` port.

## Required behavior

- Refuse before worktree execution when the command is not running inside tmux.
- Resolve the invoking window and preflight capacity for both panes before creating either pane.
- Create exactly one pane for `control_raw` and one for `workflow_full`; keep the invoking pane focused.
- Bind stable pane IDs to the run and arm and verify those bindings before reuse.
- Reuse each pane across all phases and retries rather than growing the window or creating detached sessions.
- Launch the provider command through a foreground helper that tees stdout/stderr to the pane and bounded evidence files.
- Use a result handoff written atomically so the coordinator cannot read partial JSON.
- Forward termination, interrupt, and hangup signals to the provider process group.
- Reclaim stale panes only when they remain bound to the same run; never kill a pane rebound to another run.

## Acceptance criteria

A planned run creates two and only two additional panes in the launching window, both arms visibly stream output, pane IDs are stable across transitions, durable evidence remains bounded, and cancellation leaves no provider child process.

## Tests and evidence

Add focused invariants for two-pane count, same-window target, capacity preflight, binding validation, shell-safe respawn, visible output, atomic result handoff, and process-group termination. The phase gate must also execute an installed benchmark from a real tmux pane.

## Non-targets

Do not add a new terminal backend, create one pane per phase, interpret pane capture as authoritative evidence, or make model commands depend on an interactive TTY protocol when their supported batch/streaming CLI is sufficient.

## Stop conditions

Stop if exact same-window topology cannot be proven, a partial pane layout can be created after failed preflight, output remains file-only, or provider children can outlive their pane helper.
