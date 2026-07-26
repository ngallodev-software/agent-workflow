# Session restore

**Repository:** `/lump/apps/agent-workflow`  
**Snapshot date:** 2026-07-25
**Branch:** `master`
**Version:** `0.2.2`
**Current commit:** `a62a24c` (`merge determinism security backlog overlay`)

## Current state

The overlay archive `agent-workflow-0.2.2-determinism-security-backlog-prompt-packs-changes.tar.zst` was extracted and merged. Existing local installer/uninstaller behavior was retained and reconciled with the overlay; the new `release-drift-auditor` skill is discovered dynamically. The archive was verified path-by-path and deleted.

Overlay content now present includes:

- deterministic-enforcement-foundations prompt pack;
- execution-isolation-and-secrets prompt pack;
- public-beta-trust-and-release prompt pack;
- updated `mcp-server-next` pack;
- determinism/security hardening plan and dependency/parallelism diagrams;
- release-drift-auditor skill;
- release-audit, documentation, and delegation-protocol updates.

`BACKLOG.md` is canonical. HARD-001 through HARD-010, REL-003/004, and MCP-003 now have explicit pack ownership and sequencing. Local Jenkins/release follow-up remains tracked as REL-005 through REL-007. The MCP mutation pack remains blocked behind HARD-004, HARD-005, and HARD-007.

## Verification

- `python3 scripts/audit-release-assets.py --write-manifest`: passed.
- `python3 scripts/audit-release-assets.py`: passed.
- shell syntax checks for installer/uninstaller and scripts: passed.
- all four prompt packs validated: passed.
- `python3 -m build --wheel --no-isolation`: passed; built `dist/agent_workflow-0.2.2-py3-none-any.whl`.
- global host install: passed with `./install.sh --python /home/nate/.pyenv/shims/python3 --extras mcp`.
- installed checks: `agent-workflow --version`, `agent-workflow-mcp --help`, all three release-drift-auditor skill links, host assets, and man page passed.
- no test files were modified.

The full release gate ran in an isolated test environment and ended with `33 passed, 2 skipped, 1 xfailed, 2 failed`. The two existing acceptance failures are:

1. interactive-agent reuse requires a live agent pane;
2. workflow resume reports no authoritative child run.

Both failures reproduce in isolation. They are outside the overlay’s source scope, which changed documentation, prompt packs, skills, audit scripts, and packaged prompt-root assets, not runtime implementation or tests. The expected failure is the existing BKL-002 late-steering journey.

The global install intentionally used only the `mcp` extra. Installing the optional evaluator stack globally previously introduced dependency conflicts with unrelated host applications; evaluator assets are still synchronized by the installer.

## Working tree and next work

The overlay changes are committed in `a62a24c`; the checkout is clean and is six commits ahead of `origin/master`. Do not modify tests unless explicitly authorized. Next work is the P0 hardening sequence: HARD-001/HARD-002 first, then HARD-004/HARD-005, followed by the isolation, identity, drift, and supply-chain gates. Keep MCP-003 blocked until its prerequisites are accepted.

Useful restart commands:

```bash
cd /lump/apps/agent-workflow
git status --short --branch
git log -3 --oneline
agent-workflow doctor
python3 scripts/audit-release-assets.py
```
