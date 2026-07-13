# Release Validation

Release: `agent-workflow` 0.1.0  
Validation date: 2026-07-13

## Completed checks

- Python source compiled with `python3 -m compileall -q src`.
- All shell launchers, installers, compatibility wrappers, and portable prompt-pack scripts passed `bash -n`.
- Sixteen focused unit and integration-seam tests passed.
- Tests cover CLI parsing, global-option placement, configuration loading, constrained-YAML fallback parsing, prompt-pack validation, deterministic scaffold structure, generated-runner execution and status recording, durable launch evidence, and Git worktree creation/removal.
- The source-link installer was exercised in an isolated temporary `HOME`.
- A generated three-phase prompt pack was validated, archived twice, and compared for deterministic output.
- The release archive was tested with `zstd -t`, extracted, verified against its internal `MANIFEST.sha256`, and tested again from the extracted tree.

## Environment limitation

The build environment did not contain `tmux`, so a live detached-terminal launch was not possible here. The tmux boundary is isolated behind a small adapter. Launch preparation was tested with that adapter mocked, and the generated runner itself was executed for real to verify prompt piping, output logging, exit-code propagation, and atomic status finalization.

Run the following after installing on the target machine:

```bash
agent-workflow doctor
agent-workflow launch smoke-test /path/to/clean/worktree /tmp/smoke-prompt.md -- bash -lc 'cat >/dev/null; echo smoke-ok'
agent-workflow status smoke-test --capture
agent-workflow attach smoke-test
```

A very fast command may finish before attachment; its durable log and status should still be available.

## Release check

From the source repository:

```bash
./scripts/release-check.sh
```
