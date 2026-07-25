# Command Reference

```text
agent-workflow --version
agent-workflow doctor
agent-workflow config show
agent-workflow worktree create REPO TICKET BASE [--dest PATH] [--branch NAME] [--allow-dirty]
agent-workflow worktree list REPO
agent-workflow worktree remove REPO WORKTREE [--delete-branch] [--force]
agent-workflow launch SESSION WORKDIR PROMPT [--agent-name NAME] [--agent-class CLASS] [--executor NAME] [--model MODEL] [--structured|--interactive|--no-interactive] [--allow-no-go-model] [--pane-limit-action prompt|close-idle|non-interactive|cancel] [--evaluation PLAN] [--tier low|medium|high|critical] [--allow-dirty]
agent-workflow launch SESSION WORKDIR PROMPT -- COMMAND...
agent-workflow list
agent-workflow status SESSION [--capture N]
agent-workflow attach SESSION
agent-workflow tail SESSION [--lines N]
agent-workflow steer SESSION TEXT --actor ID
agent-workflow progress SESSION TEXT --actor ID
agent-workflow ack SESSION MESSAGE_UUID TEXT --actor ID
agent-workflow agent context SESSION
agent-workflow agent task-complete SESSION --actor ID --summary TEXT [--tag TAG] [--file PATH]
agent-workflow agent candidates WORKDIR [--ticket ID] [--pack ID] [--retry-of ID] [--agent-class CLASS] [--tag TAG]
agent-workflow agent reuse SESSION PROMPT --actor ID [--ticket ID] [--pack ID] [--retry-of ID] [--tag TAG]
agent-workflow agent auto-reuse WORKDIR PROMPT --actor ID [--ticket ID] [--pack ID] [--retry-of ID] [--agent-class CLASS] [--tag TAG]
agent-workflow watch SESSION [--after SEQUENCE] [--timeout SECONDS]
agent-workflow interrupt SESSION
agent-workflow terminate SESSION [--grace-seconds N]
agent-workflow kill SESSION
agent-workflow restart SESSION [--new-session NAME]
agent-workflow review SESSION --actor ID --reason TEXT
agent-workflow accept SESSION --actor ID --reason TEXT --revision SHA
agent-workflow reject SESSION --actor ID --reason TEXT
agent-workflow ledger PACK [--runs-root PATH] [--output PATH]
agent-workflow eval validate PLAN [--pack PACK]
agent-workflow eval score RUN [--output-dir PATH] [--oracle-root PATH]
agent-workflow eval report RUN [--format json|markdown] [--output PATH]
agent-workflow eval inspect PROMPT --executor codex|claude --model MODEL --dockerfile FILE --log-dir DIR
agent-workflow eval swebench-prediction RUN --instance-id ID --model MODEL --output FILE.jsonl
agent-workflow completion bash|zsh|tcsh
agent-workflow pack scaffold DEST [--phases N] [--name NAME]
agent-workflow pack validate SOURCE [--skip-checksums]
agent-workflow pack checksum SOURCE
agent-workflow pack archive SOURCE OUTPUT.tar.zst
```

Use global `--json` or `--config PATH` before or after the subcommand. Options after an explicit launch `--` belong to the delegated command.

`doctor` is offline: executor capability probes invoke only local `--version` and `--help` commands. It performs no authentication probe or model call.

`steer`, `progress`, and `ack` append validated, fsync'd records to the active
run. `watch` blocks until a new record is durable (or its optional timeout).
They do not claim an arbitrary one-shot executor received a late prompt: a
steer becomes applied only when a child writes a correlated acknowledgement.
Interactive panes accept native terminal input, but durable steering is not
automatically injected as keystrokes. Codex configuration uses Codex nouns
such as `--sandbox` and, for the interactive TUI only,
`--ask-for-approval`; `codex exec` does not accept that approval flag. Claude
configuration uses Claude nouns such as `--permission-mode`, `--allowedTools`,
and `--disallowedTools`. Configure command-mode differences with
`interactive_permission_args` and `non_interactive_permission_args`.
Configured model allowlists are executor-specific, and no-go models require
the explicit, provenance-recorded `--allow-no-go-model` launch permission.

`agent task-complete` is the only transition from `busy` to
`idle_reusable`. `agent reuse` records a pending assignment and steer;
correlated `ack` moves it to `busy`. `agent auto-reuse` selects only exact
ticket/retry lineage and returns `action: launch` when none exists. Candidate
ranking never permits cross-worktree reuse.

`[terminal].max_interactive_agent_width` defaults to `2` and
`max_interactive_agent_vertical` defaults to `3`, producing a six-agent grid.
Agent columns are created horizontally first, then vertical slots are balanced
across those columns. Capacity is checked before pane creation and rechecked
while splitting. Agent names are globally unique
across interactive and detached active runs; a retry receives another available
name when its original run is still active.
At the pane cap, the default attached-CLI behavior prompts to close explicitly
idle panes, launch detached/non-interactive, or cancel. Non-TTY and JSON callers
fail closed unless an action is supplied; busy panes are never auto-closed.
