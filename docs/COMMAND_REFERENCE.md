# Command Reference

```text
agent-workflow --version
agent-workflow doctor
agent-workflow config show
agent-workflow worktree create REPO TICKET BASE [--dest PATH] [--branch NAME] [--allow-dirty]
agent-workflow worktree list REPO
agent-workflow worktree remove REPO WORKTREE [--delete-branch] [--force]
agent-workflow launch SESSION WORKDIR PROMPT --executor NAME [--structured] [--evaluation PLAN] [--tier low|medium|high|critical] [--allow-dirty]
agent-workflow launch SESSION WORKDIR PROMPT -- COMMAND...
agent-workflow list
agent-workflow status SESSION [--capture N]
agent-workflow attach SESSION
agent-workflow tail SESSION [--lines N]
agent-workflow steer SESSION TEXT --actor ID
agent-workflow progress SESSION TEXT --actor ID
agent-workflow ack SESSION MESSAGE_UUID TEXT --actor ID
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
