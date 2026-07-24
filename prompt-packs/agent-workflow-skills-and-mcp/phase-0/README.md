# Phase 0 — P0 skill and CLI integration

## Objective

Fix BKL-006. Create one orchestration skill, update existing workflow skills,
connect the canonical runbook/protocol references, and make the installer skill
discovery policy explicit and tested. Do not implement MCP or alter durable
control semantics.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P0-00 | C | read-only | none | coordinator review |
| P0-01 | B | medium | P0-00 | independent gate |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

## Phase-wide constraints

Native host subagents are not `agent-workflow` runs unless an explicit bridge
invokes the CLI. Direct all durable launches through `agent-workflow launch`;
do not use raw tmux lifecycle commands.

## Required references

- `docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md`
- `BACKLOG.md` BKL-006
- `docs/COMMAND_REFERENCE.md` and `docs/DELEGATION_LIFECYCLE.md`

## Exit gate

Run targeted skill/installer tests, `PYTHONPATH=src pytest -q`, and
`scripts/release-check.sh`. Manually inspect discovery-root ownership behavior
and the skill's decision/tmux language.
