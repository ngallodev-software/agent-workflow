# Delegation runbook

```bash
agent-workflow doctor
agent-workflow pack validate prompt-packs/chatgpt-sealed-run-assessment
agent-workflow worktree create /path/to/repository CHATGPT-EVAL-001 HEAD
agent-workflow launch chatgpt-eval-001 /path/to/worktree prompt-packs/chatgpt-sealed-run-assessment/phase-0/tickets/CHATGPT-EVAL-001-sealed-evidence-eval.md --ticket CHATGPT-EVAL-001 --pack chatgpt-sealed-run-assessment --executor codex --structured --no-interactive
agent-workflow status chatgpt-eval-001 --capture 60
agent-workflow review chatgpt-eval-001 --actor reviewer --reason "Independent evidence and focused gates checked"
```

Phase 1 uses a separate worktree/session and launches only after phase-0 review. Integrate only after inspecting the complete diff and rerunning shared tests. Terminate completed sessions through `agent-workflow terminate` and verify `tmux_alive=false`.
