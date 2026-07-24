# Session Restore — agent-workflow

## Resume point

- Repository: `/lump/apps/agent-workflow`
- Branch: `master`
- Remote: `origin` → `https://github.com/ngallodev-software/agent-workflow.git`
- Baseline before this restore checkpoint: `bf388be docs: add skills and mcp research handoff`
- Working tree: clean at handoff creation.
- Installed user package: editable `agent-workflow 0.1.6`.
- Installed command check: `agent-workflow --version` → `0.1.6`.
- Last doctor result: `agent-workflow doctor --json` returned `ok: true`.

## What landed

1. Durable JSONL-first control records, best-effort bounded tmux wakeups,
   visible child panes when launched from a current tmux window, normalized
   metrics, immutable trial evidence, and `eval collect`/`eval compare`
   (`6b61cbb`, release `0.1.5`).
2. The installer now performs an editable user install with core dependencies,
   preserves a pip-managed launcher, and supports `--extras` (`306c6f5`,
   release `0.1.6`).
3. [BACKLOG.md](BACKLOG.md) is the only active task register (`b6a55c2`).
4. P0 BKL-006 was recorded because agents lack a skill-level operational path
   to the `agent-workflow` CLI, runbook, protocol, and tmux behavior.
5. A ChatGPT handoff pack and matching clean source archive were created and
   validated (`bf388be`).

## Immediate next work

### Preferred: execute the prepared handoff

Give ChatGPT both archives below. It must follow the prompt pack in order:

1. Phase 0: `P0-00`, then `P0-01`; implement **only** BKL-006.
2. Phase 1: research only; produce `docs/MCP_SERVER_DECISION.md`; do not
   implement an MCP runtime until the decision memo is reviewed.

Artifacts:

- `dist/agent-workflow-skills-and-mcp-prompt-pack.tar.zst`
  - SHA-256: `3c60ffd3730d89507b98bf36fc3cdecd92c5a602b6241ab416fd8d8ed141ffe5`
- `dist/agent-workflow-0.1.6-skills-mcp-source.tar.zst`
  - SHA-256: `315c3f604a46fd376e0fbd1a12d081ca38826411b52784af4ee35e3d62a2ee8c`
  - Clean Git archive, about 512 KiB compressed.

### P0 scope summary

Read [docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md](docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md).
The fix must add an `agent-workflow-orchestrator` skill, connect the three
existing skills to it, document safe CLI lifecycle/tmux behavior, and make
skill-install discovery roots explicit and tested. Native host subagents must
remain clearly distinct from durable `agent-workflow` runs unless an explicit
bridge exists.

### MCP research guardrails

Read `P1-00-mcp-server-decision.md` in the pack. The decision must use primary
sources, prefer a local stdio-first minimal surface if MCP is recommended, keep
sealed receipts/control logs authoritative, avoid arbitrary shell/tmux tools,
and never claim executor steering delivery from terminal text.

## Other active work

Use [BACKLOG.md](BACKLOG.md) rather than historical plans. Highest priorities:

- `BKL-001`: durable consumer cursors and idempotent control handling.
- `BKL-006`: skill/CLI/runbook integration (prepared handoff above).
- `BKL-002`: executor-specific late-steering adapter.
- `BKL-003`–`BKL-005`: provider evidence calibration and real benchmark cohort.
- `BKL-010`: visual evaluation, blocked on pinned browser/font/evidence inputs.
- `DEC-001`–`DEC-003`: durability, benchmark, and multi-host decisions.

## Validation commands

```bash
PYTHONPATH=src python3 -m pytest -q
bash scripts/release-check.sh
PYTHONPATH=src python3 -m agent_workflow pack validate prompt-packs/agent-workflow-skills-and-mcp
agent-workflow doctor --json
```

## Notes for the next agent

- The user explicitly wants agents in visible panes when the orchestrator is
  already in tmux. The implementation supports this only through
  `agent-workflow launch`; host-native subagent spawning is separate.
- Use `./install.sh` for a user-global editable install with core dependencies.
  Optional extras: `./install.sh --extras eval,stats` or `--extras all`.
- Preserve user changes in a dirty worktree. Use `apply_patch` for edits.
- Do not add a broker, daemon, database, or MCP runtime without an approved,
  bounded ticket and the MCP decision review.
