# P0-01 — Make agent-workflow operationally discoverable

## Objective

Implement BKL-006 and `docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md`. A fresh
supported agent must discover a repo-owned orchestration skill, know exactly
when to use the `agent-workflow` executable, and have accurate tmux and
native-subagent boundaries.

## Required reading

- `docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md`
- `BACKLOG.md` BKL-006
- `docs/COMMAND_REFERENCE.md`, `docs/DELEGATION_LIFECYCLE.md`, and
  `docs/PROMPT_PACK_STANDARD.md`
- `skills/*/SKILL.md`, `install.sh`, and `tests/test_install_uninstall.py`
- `src/agent_workflow/sessions.py` and `tmux.py` only to verify real behavior

## Required implementation

1. Add `skills/agent-workflow-orchestrator/SKILL.md` with a precise trigger
   description, decision table, safe command patterns, lifecycle/recovery
   steps, tmux current-window behavior, and the semantic-steering limitation.
2. Update the three existing workflow skills to cross-link the orchestration
   skill and correct CLI/runbook behavior without duplicating large manuals.
3. Make the installation/discovery policy explicit in `install.sh` and docs.
   Detect and test intended Codex, Claude, and shared-agent roots. Preserve
   unrelated files and avoid duplicate-name ambiguity.
4. Add narrow tests for skill metadata, install ownership/idempotence, and
   canonical command/reference claims.
5. Update `BACKLOG.md` only to mark BKL-006 done after all exit evidence
   passes; do not close unrelated tasks.

## Writable paths

`skills/`, `install.sh`, `README.md`, `docs/INSTALLATION.md`,
`docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md`, `BACKLOG.md`, narrowly needed
tests, and release manifest. Do not change `src/agent_workflow/` except for a
demonstrated documentation/CLI discovery defect with a focused test.

## Acceptance criteria

- A supported agent can locate the skill and execute the documented happy path.
- The skill says native host subagents are not workflow runs unless bridged.
- It directs tmux users to `agent-workflow launch`, never raw tmux creation.
- The installer policy is safe, testable, and documented for each target root.
- Existing skills agree with the canonical command reference.
- Full release checks pass.

## Stop conditions

Stop if target-host skill discovery cannot be verified or conflicts between
skill roots cannot be made safe. Record the exact host behavior; do not write
an untested claim or delete user-owned skills.
