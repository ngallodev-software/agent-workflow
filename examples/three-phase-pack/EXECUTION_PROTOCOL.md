# Execution Protocol

Each delegated ticket is executed as an Agent Run. The pack describes task dependencies, expected results, and evaluation policy without assuming an interactive host.

For headless execution:

```bash
agent-workflow agent-run prepare RUN WORKTREE PROMPT --worker-mode headless
agent-workflow agent-run start RUN
```

For a future externally hosted worker, prepare with `--worker-mode external` and let the external integration consume the launch plan.

Durable messages, completion, evidence, evaluation, review, and acceptance remain agent-workflow authority in either mode.
