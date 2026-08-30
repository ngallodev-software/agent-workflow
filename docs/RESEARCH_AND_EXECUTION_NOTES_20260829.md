# Research and execution notes — 2026-08-29

## Terminal observation

`ps` found no live `agent-workflow`, Luna, Codex, tmux, or terminal worker for
the completed execution. `agent-workflow agent-run status --json` reports
terminal durable states and `worker_alive: false` for the completed/failed
runs. This rules out a live worker leak. The visible background terminals are
external-host projections that are not retired after the durable state becomes
terminal; `TERM-001` tracks the host-binding solution.

## Execution-evidence review

- `TASK-001-a3b4d261` and retry are sealed failed runs: their completion
  evidence was invalid (uncommitted change, then placeholders). They cannot
  satisfy the dependency.
- The dependency-bypassed review was useful evidence but its deterministic
  evaluation failed; it is not acceptance.
- The final review correctly requests changes: live watcher continuity,
  duplicate delivery/restart evidence, exact five-field NOTIFY-001 contract,
  and revision-matching hashes are incomplete.
- The prompt pack's `EVAL-002` uses selector terms that match no test names,
  producing pytest exit code 5 even though the full focused file passed.

## CLI and environment observations

- `rtk find` rejects compound `find` predicates/actions. Used plain `find`
  only for those incompatible queries.
- A first `apply_patch` attempt in this work failed due invalid hunk framing;
  it made no file change. The corrected patch follows normal patch framing.
- `agent-run prepare` rejected review research runs without `--tier`; retrying
  with the tier then revealed that automatic name selection reused `bridge`.
  Failed name reservation left status-less partial run directories, directly
  reproducing `TERM-001`/`EXEC-001`.
- `rtk find` rejects compound `find` predicates/actions. Used plain `find`
  only for those incompatible queries.
- A delegated broad inspection attempted to read control-intent directories as
  files and produced harmless `Is a directory` errors; no source was changed.
- There were no live worker processes when inspected, so no process was killed
  or terminal forcibly closed.
