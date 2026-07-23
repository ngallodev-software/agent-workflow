# Release Validation

Release: `agent-workflow` 0.1.2
Validation date: 2026-07-17

## Automated gates

- `bash scripts/release-check.sh`: passed.
- `pytest -q`: 72 passed.
- `ruff check src tests scripts`: passed.
- `shellcheck install.sh uninstall.sh bin/agent-workflow scripts/*.sh`: passed.
- Python compilation covered `src`, `tests`, and `scripts`.
- Release audit validated TOML, YAML, JSON, schemas, Markdown links, skill frontmatter, versions, executable modes, explicit portable-asset mirrors, placeholders, and full manifest coverage, including removal of duplicate `.orig` trees.
- Example three-phase pack validated with a complete internal checksum manifest.

## Install and artifact gates

- Installer/uninstaller tests passed in isolated temporary homes, including preservation of unrelated files and symlinks.
- Wheel `agent_workflow-0.1.2-py3-none-any.whl` is the release artifact; build/install verification must report version `0.1.2` from both CLI and import.
- The `eval` extra installed in an isolated virtual environment at pinned `inspect-ai==0.3.247` and `inspect-swe==0.2.66`; both public Codex/Claude task factories constructed successfully and the minimal Docker image built successfully.
- Generated Bash completion contained the current `swebench-prediction` command.
- Example pack archived twice to byte-identical `.tar.zst` files, passed `zstd -t`, extracted, and revalidated from the extracted tree.

## Live executor gates

Both configured executors received bounded no-write tasks through real tmux-backed structured `agent-workflow launch` runs:

| Executor | Session | Command | Result |
|---|---|---|---|
| Codex 0.144.5 | `aw-live-codex-0717b` | `codex exec --sandbox workspace-write --skip-git-repo-check --json -` | returned `CODEX_LAUNCH_OK`; completed, exit 0 |
| Claude Code 2.1.212 | `aw-live-claude-0717c` | `claude --print --verbose --output-format stream-json` | returned `CLAUDE_LAUNCH_OK`; completed, exit 0 |

Each run preserved raw structured events and separate stderr, then produced a verified 12-artifact final seal. Original prompt copies and SHA-256 receipts remained separate from generated launch context. Offline doctor reported both executors installed with supported structured-output flags.

## Evaluation gates

- Missing required collectors, fabricated or empty score sets, receipt-manifest rewrites, escaping symlinks, nested repositories, ignored-file mutations, unknown task/oracle references, and unpaired winner claims fail closed.
- Baseline/post collection order, committed/staged/unstaged/untracked attribution, JUnit pass-to-fail regression attribution, evidence-fidelity claims, budget timeout, missing-executor recovery, evaluated retry provenance, high-risk independent review, and byte-stable rescoring have focused regression tests.
- Three public development fixtures fail under no-op and pass their reference change. External oracle IDs and hashes are pinned; canaries and hidden checks remain outside the repository.
- Inspect, official SWE-bench harness execution, OTel export, and MLflow backend runs remain explicit experimental/operator-run lanes; this validation covers their import/format seams, not paid models or external services.

## Run the release gate

```bash
./scripts/release-check.sh
```
