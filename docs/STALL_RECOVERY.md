# Stall Recovery

A session is potentially stalled when tmux is alive and its log has not grown for the configured interval. This signal is deliberately conservative.

## Inspect

```bash
agent-workflow status SESSION --capture 100
agent-workflow attach SESSION
```

Classify:

- waiting for operator input;
- package or network operation;
- test/build deadlock;
- repeated agent reasoning loop;
- legitimate long-running command with quiet output;
- child process detached from the pane.

## Recover

1. Interrupt with Ctrl-C.
2. Record the reason in completion notes.
3. Correct the environment or prompt.
4. Restart into `SESSION-retryN`.
5. Do not erase the original log.

Automatic timer-based killing is intentionally excluded from v0.1.
