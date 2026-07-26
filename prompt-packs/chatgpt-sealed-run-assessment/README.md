# chatgpt-sealed-run-assessment

This pack gives ChatGPT a durable, evidence-first continuation task: analyze the sealed foundation and hook runs, repair or extend the evaluation system where the evidence contract is incomplete, and then generate strict TDD installed-product journeys for future planned work.

The complete initial prompt is [`CHATGPT_INITIAL_PROMPT.md`](CHATGPT_INITIAL_PROMPT.md). It includes the prior ChatGPT starting prompt verbatim followed by the new continuation mission.

## Evidence inputs

- [`references/sealed-run-evidence.md`](references/sealed-run-evidence.md)
- [`references/sealed-runs/`](references/sealed-runs/)
- [`references/deterministic-foundation-ledger.tsv`](references/deterministic-foundation-ledger.tsv)
- Current source, [`BACKLOG.md`](../../docs/BACKLOG.md), and the current evaluation contracts/tests.

## Execution

Validate and launch through the CLI:

```bash
agent-workflow pack validate prompt-packs/chatgpt-sealed-run-assessment
agent-workflow worktree create /path/to/repository CHATGPT-EVAL-001 HEAD
agent-workflow launch chatgpt-eval-001 /path/to/worktree prompt-packs/chatgpt-sealed-run-assessment/phase-0/tickets/CHATGPT-EVAL-001-sealed-evidence-eval.md --ticket CHATGPT-EVAL-001 --pack chatgpt-sealed-run-assessment --executor codex
```

Use separate worktrees and durable sessions for each phase. A valid current tmux context produces a visible pane through `agent-workflow launch`; an unusable context falls back to a detached named session. A native host subagent is not a durable workflow run unless it is explicitly bridged through the CLI.

Phase 1 depends on the reviewed output of phase 0. Do not mark strict future tests as passing merely because they are generated.
