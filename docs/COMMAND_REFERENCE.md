# Command Reference

```text
agent-workflow --version
agent-workflow doctor
agent-workflow config show
agent-workflow worktree create REPO TICKET BASE [--dest PATH] [--branch NAME]
agent-workflow worktree list REPO
agent-workflow worktree remove REPO WORKTREE [--delete-branch] [--force]
agent-workflow launch SESSION WORKDIR PROMPT --executor NAME [--allow-dirty]
agent-workflow launch SESSION WORKDIR PROMPT -- COMMAND...
agent-workflow list
agent-workflow status SESSION [--capture N]
agent-workflow attach SESSION
agent-workflow tail SESSION [--lines N]
agent-workflow interrupt SESSION
agent-workflow terminate SESSION [--grace-seconds N]
agent-workflow kill SESSION
agent-workflow restart SESSION [--new-session NAME]
agent-workflow pack scaffold DEST [--phases N] [--name NAME]
agent-workflow pack validate SOURCE [--skip-checksums]
agent-workflow pack checksum SOURCE
agent-workflow pack archive SOURCE OUTPUT.tar.zst
```

Use global `--json` or `--config PATH` before or after the subcommand. Options after an explicit launch `--` belong to the delegated command.
