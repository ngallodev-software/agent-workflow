# Session restore

**Repository:** `/lump/apps/agent-workflow`  
**Snapshot date:** 2026-07-28
**Branch:** `master`
**Version:** `0.2.5`
**Current integration:** foundation hardening, sealed-run assessment, durable pane/process guidance, and verified-run archival are present in the current checkout.

## Current state

The foundation implementation runs were sealed, integrated, and independently gated. HARD-001, HARD-002, HARD-004, HARD-005, and HARD-008 are recorded as completed in the canonical backlog. No score/report/score-set evidence was fabricated: runs without an evaluation plan remain evaluation-unavailable.

The latest process work adds a recoverable `agent-workflow archive` command (with `clear` alias) for accepted runs, plus a read-only completion template and explicit interactive-versus-structured closeout instructions. No active child agent should be assumed from terminal prose; verify with `agent-workflow list` and the tmux identity checks.

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

- `python3 scripts/audit-release-assets.py`: passed; mutable checksum manifests are ignored and not part of the repository gate.
- focused invariant checks: `9 passed`.
- installed archive acceptance journey: `1 passed`; it required explicit tmux closeout before moving the accepted run.
- `python3 -m build --wheel --no-isolation`: passed; built `agent_workflow-0.2.5-py3-none-any.whl`.
- final codebase-memory index: `6996` nodes and `12586` edges, with the persistent graph artifact present.
- repository-wide pytest was attempted twice but did not return a result; do not claim a full-suite pass from this handoff. Re-run it as a bounded investigation in the new session.

## Working tree and next work

The checkout is `master` ahead of `origin/master` by 36 commits and has
uncommitted process/docs/test changes from this session; inspect the diff before
integrating or committing. No commit was made for this session. The next work
should start from the canonical `docs/BACKLOG.md`; keep MCP-003 blocked until
its prerequisites are accepted.

## Live runtime observations

The temporary R9 review session used during this turn was terminated and its
tmux pane/session closed. The current inventory still contains one unrelated
orphaned `running` projection, `tax-p1-sec-001-r5-review`; inspect it before
claiming the host is quiescent. No implementation child is active for this
turn.

## New-session startup: Terra

This is the handoff for a new orchestrator session. Start from the repository
root and let the new session verify the current checkout before taking scope:

```bash
cd /lump/apps/agent-workflow
python3 -m pip install --user --force-reinstall --no-deps dist/agent_workflow-0.2.5-py3-none-any.whl
git status --short --branch
agent-workflow doctor
agent-workflow list --json
agent-workflow archive --all-verified --dry-run --json
```

The host currently reports `agent-workflow 0.2.5`, but its installed parser
does not yet expose the newly built `archive` command. Install the wheel above
before using the new command, or temporarily prefix commands with
`PYTHONPATH=/lump/apps/agent-workflow/src python3 -m agent_workflow.cli`.

For the next bounded implementation, use a dedicated worktree and launch the
implementation agent interactively with Terra:

```bash
agent-workflow worktree create /lump/apps/agent-workflow TICKET-ID master
agent-workflow launch SESSION-ID /path/to/worktree /path/to/prompt.md \
  --ticket TICKET-ID --pack /path/to/prompt-pack \
  --agent-class implementation --executor codex --model gpt-5.6-terra
```

Implementation is interactive by default. If the pane limit is full, stop and
choose explicitly between closing an idle pane, using a structured
non-interactive run when post-run evaluation is required, or cancelling. Do
not silently downgrade the launch. Terra is a configured model choice, not a
replacement for the worktree, handoff, receipt, review, acceptance, and close
gates.

Useful restart commands:

```bash
cd /lump/apps/agent-workflow
git status --short --branch
git log -3 --oneline
agent-workflow doctor
python3 scripts/audit-release-assets.py
```
