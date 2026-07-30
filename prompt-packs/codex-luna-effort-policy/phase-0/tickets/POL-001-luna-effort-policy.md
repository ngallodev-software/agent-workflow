# POL-001 — Codex Luna effort policy

## Objective

Make automatic Codex selection fail closed unless it resolves to
`gpt-5.6-luna` and a configured reasoning effort of `low`, `medium`, or
`high`. The effort must be passed to the Codex command deterministically and
recorded in the executor plan and launch evidence. Do not select another Codex
model when a task seems difficult; improve task decomposition and ticket
detail instead.

## Required preflight

Read `docs/references/WORKTREE_PREFLIGHT.md` and complete its exact-worktree
preflight before source discovery or edits. Read the current config, executor,
session, CLI, routing, tests, example config, and operator documentation.

## Writable scope

`src/agent_workflow/config.py`, `executors.py`, `sessions.py`, `cli.py`,
`routing.py` only if needed for enforcement, focused tests, the example config,
`docs/COMMAND_REFERENCE.md`, `docs/OPERATIONS.md`, `docs/BACKLOG.md`,
`CHANGELOG.md`, and this prompt-pack handoff. Do not change unrelated executor
semantics, authenticated identity policy, MCP behavior, or prompt-pack
ownership.

## Required behavior

- Codex automatic/default and configured-class selection accepts only
  `gpt-5.6-luna`; remove Mini, Terra, Sol, and wildcard bypasses from shipped
  automatic selection.
- Add a configuration and launch representation for exactly `low`, `medium`,
  and `high` Luna reasoning efforts, with `medium` as the shipped default.
- Reject absent, invalid, or non-Luna Codex automated selections before any
  child process starts. Ensure explicit Codex commands cannot evade the policy.
- Pass effort through the supported Codex CLI configuration surface, and record
  the selected model and effort in immutable launch/plan evidence.
- Preserve manual selection of a non-Codex executor command as an explicit
  operator action; do not make it appear as an automatic Codex recommendation.
- Update user-facing configuration and command documentation: hard tasks are
  to be subdivided, not promoted to a different automatic model.

## Evidence

Add a focused installed-product journey covering default low/medium/high
selection, invalid effort rejection, non-Luna rejection, explicit-command
evasion rejection, and evidence recording. Retain only compact unit/invariant
coverage needed to protect parser/config and command construction boundaries.
Run focused tests, `python3 scripts/audit-release-assets.py`, and pack
validation. Record exact commands, results, and unresolved limitations.

## Acceptance criteria

- all automatic Codex selections are Luna with one allowed effort;
- invalid models, missing/invalid efforts, and explicit-command bypasses fail
  before executor launch;
- selected effort is present in launch evidence and Codex argv;
- focused installed and invariant evidence passes.

## Stop conditions

Stop and report if the installed Codex CLI does not support a deterministic
effort option, if the proposed behavior requires silent model promotion, or if
the change would turn a manually supplied non-Codex command into an automatic
routing choice.

## Handoff

Use `templates/TICKET_COMPLETION.md`. State the exact Codex argument used for
effort, evidence fields, rejected inputs, and whether the installed-product
journey executed the selected command or used a controlled executable fixture.
