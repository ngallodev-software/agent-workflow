# Repository assessment

Reviewed: 2026-07-17

## Resolved in current working tree

- Release audit now excludes VCS, caches, graph artifacts, archives, and removed backup trees while enforcing complete manifest coverage.
- `scripts.orig/` and `templates.orig/` were removed; intended packaged mirrors are explicit and byte-checked.
- Pack validation rejects escaping prompt paths and missing, incomplete, duplicate, extra, or mismatched checksum entries.
- Session kill preserves terminal evidence; worktree provenance records the requested base revision.
- Config parsing rejects invalid integer/boolean types; Codex defaults support non-Git workdirs and Claude structured mode includes its required verbose flag.
- Inert configuration fields were removed so `config show` reports only active behavior.
- Launches expose durable session, prompt-pack, prompt-source, and completion-report paths to both executors.
- Installer/uninstaller link handling is portable and refuses unrelated paths.
- Versioned contracts, structured executor streams, baseline/post collectors, deterministic scorers, sealed receipts, lifecycle review, and evaluation reports now have adversarial regression coverage.
- README/config/runbook/version history and validation evidence match current behavior.
- Canonical release gate, plain pytest, Ruff, ShellCheck, deterministic archive, wheel install, optional Inspect imports, and live Codex/Claude structured smoke runs pass.

## Deliberate boundaries

- Runtime remains POSIX/tmux-oriented; no daemon, web UI, remote execution, automatic merge, automatic kill, or autonomous model selection.
- Prompt-pack and script mirrors remain intentional distribution assets; release audit prevents drift.

## Future improvements

1. Add CI for the existing release gate on supported Python versions.
2. Introduce a terminal-backend interface before adding a non-tmux backend.
3. Continue splitting CLI dispatch and session orchestration when behavior changes require it.
4. Promote the experimental Inspect/SWE-bench/OTel/MLflow seams only after their external paid or service-backed validation lanes run in CI or a controlled release environment.
