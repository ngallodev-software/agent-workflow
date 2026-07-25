# Session Restore — agent-workflow

## Current checkpoint

Captured 2026-07-25 in `/lump/apps/agent-workflow`.

- Current branch: `feature/workflow-prep-for-mcp`
- Current HEAD: `c219eb77f2a4f9979292667e8596e2d9e4f3c08f` — workflow additions and fixes preparing groundwork for MCP server implementation.
- Version: `0.1.12`; `agent-workflow --version` reports `0.1.12`.
- `agent-workflow doctor --json`: `ok: true`; Codex and Claude executors are installed and detected.
- Latest Claude-default policy verification: `157 passed, 1 skipped`; release audit valid.
- ChatGPT completion pack: `dist/chatgpt-workflow-completion-next.tar.zst`
  SHA-256: `b2a2942d91ac9a6b1e8094be7b3298e6da1a52649e5d702b74e67b1951743ce5`.
- ChatGPT source archive with `.git` history:
  `dist/agent-workflow-0.1.12-chatgpt-workflow-completion-source.tar.zst`
  SHA-256: `dc52535d3236411fe321321bde6da47c6f7d8ade4b493d207ba97967230005bd`.
  It excludes Python environments/libraries, caches, build output, generated
  index/state, and prior archives. The archive passed `zstd -t` and inventory
  checks confirmed `.git/HEAD` and `.git/objects/` are present.
- Main working tree has only these untracked files:
  `CHANGED_FILES.md`, `CLEANUP_AND_REMOVAL_AUDIT.md`,
  `FEATURE_TEST_LEDGER.md`, and `REMOVED_PATHS.txt`.
- Do not reset, clean, or overwrite the dirty checkout. Preserve user changes.

## Verified foundation state

- Codebase-memory MCP was rebuilt before implementation and later refreshed:
  5,159 nodes, 11,357 edges, persistent artifact present at
  `.codebase-memory/graph.db.zst`.
- Accepted P0 workflow chain exists in the clean integration worktree:
  `/home/nate/.local/share/agent-workflow/worktrees/workflow-foundations-integration`
  at `f022cf7` (`fix: bound workflow cli filesystem errors`).
- Integration worktree tests: `178 passed, 1 skipped`.
- Integration release audit: `release assets: valid`.
- Main backlog records `WF-001`, `WF-002`, `WF-00`, `WF-01`, and `WF-02` as done.
- `BKL-006` and `BKL-008` are done. `BKL-001` and `BKL-002` remain P0 ready.
- MCP-001 and MCP-002 are done; MCP-003 remains blocked on WF-22.

## Feature test ledger

Use [FEATURE_TEST_LEDGER.md](FEATURE_TEST_LEDGER.md) as the durable feature-by-feature verification record. It records passing features and known partials, including:

- durable worktrees, model/class/no-go policy, completion contracts, workflow replay/scheduling, and codebase-memory: useful and passing;
- late steering and child progress delivery: partial because one-shot executors do not semantically consume late messages and child state writes can be read-only;
- review/accept/reject lifecycle: partial because ordinary runs currently require a score set;
- executor command safety: partial because narrowly scoped temporary cleanup was rejected by the safety filter;
- linked-worktree delegated commit/finalization: partial because the WF-10 child could not write its Git index lock.

## WF-10 status

WF-10 was implemented in an isolated worktree and committed coordinator-side as:

- `a512bb26f296c6311c8ac60e58bcec6b6644ef88` — `feat: add receipt-backed approval gates`.
- Focused approval/lifecycle/ledger tests passed: `9 passed`.
- The implementation agent reported full-suite and release-audit success, but could not finalize its completion sidecar because the linked worktree Git index was read-only.
- Independent Luna review ran against the commit and rejected it. Full review gates passed (`181 passed, 1 skipped`; release audit valid), but approval trusted the mutable `status.json` receipt path and did not prove that the receipt was the append-only artifact for the run. A copied/forged same-session receipt could therefore satisfy approval.
- WF-10 remains `ready` in `BACKLOG.md`; it is not accepted or integrated.
- Correction worktree is preserved at:
  `/home/nate/.local/share/agent-workflow/worktrees/workflow-foundations-wf-10-correction`
  based on `a512bb2`. No correction agent was launched after the stop request.
- Review and implementation sessions were terminated. Their sealed evidence remains under `/home/nate/.local/state/agent-workflow/runs/`.

## Delegation session records

Most historical sessions have detached tmux records. The latest relevant states are:

- `wf02-mini-r3-20260724`: completed, valid handoff, exit 0.
- `wf02-review-luna-r3-20260725`: completed, valid handoff, exit 0.
- `wf10-mini-20260725`: failed during finalization, exit 1, completion missing; source evidence preserved.
- `wf10-review-luna-20260725`: review result valid but session terminated after rejection, exit 1; sealed evidence preserved.

No agent should be treated as active solely because an old detached tmux session is listed. Confirm with `agent-workflow --json status <session>` and the `tmux_alive`/`observed_state` fields.

## Next work, in order

1. Correct WF-10 receipt authenticity/append-only provenance; add a regression test for copied or forged same-session receipts.
2. Run focused tests, full pytest, release audit, and an independent review. Integrate only after a valid accepted handoff.
3. Continue WF-11 result binding, then WF-12 aggregate workflow receipts, using isolated worktrees and independent review for each ticket.
4. Address P0 BKL-001 durable consumer cursors and BKL-002 executor-specific late steering according to the canonical backlog ordering.
5. Rebuild the codebase-memory index after accepted integrations.
6. Only after the requested implementation set is accepted: bump/reconcile version, build, test, install globally, and verify `agent-workflow doctor --json` and `agent-workflow --version`.

## Required operating rules

- Read `BACKLOG.md` as canonical task state.
- Use `agent-workflow` CLI launches with isolated worktrees for delegated work; do not use native subagent spawning as a substitute for durable runs.
- Follow Mini → Luna → Terra routing without skipping rungs; no-go models require explicit authorization.
- Require valid `agent-workflow/completion/v1` handoffs, exact command evidence, scope checks, manifest validation, and independent review before integration.
- Never infer semantic steering delivery from logs, terminal capture, tmux state, or keystrokes.
- Claude launches default to interactive, including exploratory/review classes; `--no-interactive` and `--structured` are explicit opt-outs. Codex class defaults remain unchanged.
- Preserve dirty user changes and use `apply_patch` for repository edits.

## Useful verification commands

```bash
cd /lump/apps/agent-workflow
agent-workflow doctor --json
agent-workflow --version
agent-workflow --json status <session-id> --capture 0
PYTHONPATH=src pytest -q
python3 scripts/audit-release-assets.py
```
