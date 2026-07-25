# Session restore checkpoint

**Release:** 0.2.1
**Branch:** `feature/workflow-prep-for-mcp`
**Checkpoint date:** 2026-07-24

## Current implementation state

- Workflow foundation tickets WF-00, WF-01, WF-02, WF-10, WF-11, WF-12, WF-20, WF-21, and WF-22 are implemented in the current working tree.
- Receipt-backed approval gates reconstruct canonical lifecycle evidence rather than trusting mutable status pointers.
- Result bindings use bounded RFC 6901 JSON Pointers over sealed ancestor results; parent snapshots and child `workflow-inputs.json` are atomically installed read-only before executor launch.
- Terminal workflows can be sealed and verified through aggregate workflow receipts.
- The three authorized templates and deterministic routing advisor are implemented.
- BKL-003 provider evidence and BKL-005 trial evidence are implemented with 0.2.1 fail-closed stream and scorer-receipt validation; BKL-004 real paid executor cohorts remain open.
- MCP-001 and MCP-002 remain implemented as a bounded read-only local stdio adapter. WF-22 is complete, so MCP-003 is now ready but not implemented.
- The unused vendored MCP SDK source tree has been removed. The optional pinned dependency is recorded in `src/agent_workflow/mcp/SDK_DEPENDENCY.md`.

## Durable authorities

- Per-run evidence lives below the configured XDG state root, normally `~/.local/state/agent-workflow/runs/<session-id>/`.
- Workflow state is reconstructed from `workflow-snapshot.json` and `workflow-events.jsonl`.
- The canonical snapshot is read-only and descriptor-validated; scheduler mutation, sealing, verification, and projection refresh share `workflow.lock`.
- `status.json`, `workflow-status.json`, logs, and tmux capture are projections/observations.
- `final-receipt.json`, lifecycle receipts, and `workflow-receipt.json` are read-only canonical seals; final-run verification returns the digest of the same receipt bytes read under `seal.lock`, workflow receipts use one stable descriptor under `workflow.lock`, and lifecycle receipt roots may not be symlinks.
- Content-addressed scorer receipts are regular, non-symlink, read-only files; lifecycle review binds the exact score-set bytes it validated.
- Authority-bearing sealed JSON is read through beneath-root descriptors and matched to its final-receipt size/hash; read-only enforcement covers required and optional artifact trees without following symlinks.

## Resume validation

From the repository root:

```bash
PYTHONPATH=src python3 -m pytest -q
python3 -m compileall -q src
bash -n install.sh uninstall.sh scripts/*.sh
python3 scripts/audit-release-assets.py
PYTHONPATH=src python3 -m agent_workflow.cli pack validate prompt-packs/chatgpt-workflow-completion-next
```

Regenerate the release manifest after any tracked content change:

```bash
python3 scripts/audit-release-assets.py --write-manifest
```

## Primary references

- `BACKLOG.md`
- `FEATURE_TEST_LEDGER.md`
- `docs/ARCHITECTURE.md`
- `docs/diagrams/REPOSITORY_CHART_PACK.md`
- `docs/PROVIDER_EVIDENCE_RESEARCH.md`
- `docs/MCP_SERVER_IMPLEMENTATION_PROPOSAL.md`
- `docs/execution-evidence/FINAL_CRITICAL_REVIEW.md`
