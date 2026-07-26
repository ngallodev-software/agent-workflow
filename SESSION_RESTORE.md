# Session restore

**Repository:** `/lump/apps/agent-workflow`  
**Snapshot date:** 2026-07-26
**Branch:** `master`
**Version:** `0.2.3`
**Current integration:** foundation hardening and ChatGPT sealed-run assessment pack are staged on `master`.

## Current state

The foundation implementation runs were sealed, integrated, and independently gated. HARD-001, HARD-002, and HARD-005 remain `in-review` pending shared acceptance; HARD-004 remains blocked. No score/report/score-set evidence was fabricated: all six sealed runs had no evaluation plan and collection failed closed on the missing score-set file.

Overlay content now present includes:

- deterministic-enforcement-foundations prompt pack;
- execution-isolation-and-secrets prompt pack;
- public-beta-trust-and-release prompt pack;
- updated `mcp-server-next` pack;
- determinism/security hardening plan and dependency/parallelism diagrams;
- release-drift-auditor skill;
- release-audit, documentation, and delegation-protocol updates.

`docs/BACKLOG.md` is canonical. Root steering is in `AGENTS.md`; conditional delegation references are in `docs/references/`. HARD-001 through HARD-010, REL-003/004, and MCP-003 retain explicit pack ownership and sequencing. Local Jenkins/release follow-up remains tracked as REL-005 through REL-007. The MCP mutation pack remains blocked behind HARD-004, HARD-005, and HARD-007.

## Verification

- `python3 scripts/audit-release-assets.py --write-manifest`: passed.
- `python3 scripts/audit-release-assets.py`: passed.
- shell syntax checks for installer/uninstaller and scripts: passed.
- all four prompt packs validated: passed.
- `python3 -m pip wheel . --no-deps`: passed; built `agent_workflow-0.2.3-py3-none-any.whl`.
- full suite: 41 passed, 12 failed, 2 skipped, 1 strict future xfail; failures remain installed-product/executor-environment limitations and are not represented as release acceptance.
- global host install: pending final 0.2.3 deployment verification with `./install.sh --python /home/nate/.pyenv/shims/python3 --extras mcp`.
- installed checks: `agent-workflow --version`, `agent-workflow-mcp --help`, all three release-drift-auditor skill links, host assets, and man page passed.
- no test files were modified.

The full release gate ran in an isolated test environment and ended with `33 passed, 2 skipped, 1 xfailed, 2 failed`. The two existing acceptance failures are:

1. interactive-agent reuse requires a live agent pane;
2. workflow resume reports no authoritative child run.

Both failures reproduce in isolation. They are outside the overlay’s source scope, which changed documentation, prompt packs, skills, audit scripts, and packaged prompt-root assets, not runtime implementation or tests. The expected failure is the existing BKL-002 late-steering journey.

The global install intentionally used only the `mcp` extra. Installing the optional evaluator stack globally previously introduced dependency conflicts with unrelated host applications; evaluator assets are still synchronized by the installer.

## Working tree and next work

The overlay changes are committed in `a62a24c`; the current handoff revision is `fd1aba1`, and the checkout is clean on `master` ahead of `origin/master`. Do not modify tests unless explicitly authorized. Next work is the P0 hardening sequence: HARD-001/HARD-002 first, then HARD-004/HARD-005, followed by the isolation, identity, drift, and supply-chain gates. Keep MCP-003 blocked until its prerequisites are accepted.

## Live runtime observations

At handoff capture, the main tmux server showed only the live orchestrator pane (`0:0.0`). Process inspection also found an active stdio MCP process from the repository virtualenv and older workflow tail/wait processes, including the `aw-model-effort-20260724` log tail. These are runtime leftovers rather than uncommitted repository work; inspect and stop them explicitly before treating the host as fully quiescent. Separate `the-tax-machine` monitoring processes were also visible and are outside this repository.

Useful restart commands:

```bash
cd /lump/apps/agent-workflow
git status --short --branch
git log -3 --oneline
agent-workflow doctor
python3 scripts/audit-release-assets.py
```
