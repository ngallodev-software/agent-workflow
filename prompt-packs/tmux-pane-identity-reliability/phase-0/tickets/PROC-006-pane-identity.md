# PROC-006 — Durable shared-window pane identity

## Delegation metadata

- Ticket: `PROC-006`
- Canonical backlog ID: `PROC-006`
- Priority/risk: P0 / critical
- Tier: A
- Dependencies: none
- Session: `tmux-pane-identity-reliability-proc-006`
- Implementation launch: interactive by default
- Independent review: required; reviewer must not be the implementer

## Objective

Fix the serious shared-window tmux identity bug. `agent-workflow` currently
stores `session:window.pane_index` as `tmux_target`, so adding or removing
other panes can make a live executor appear orphaned and block
`agent-workflow agent task-complete`. All lifecycle controls and reusable-agent
discovery must address the intended pane by durable identity.

## Required preflight

In the newly created isolated worktree, before structural discovery or edits:

1. Read `docs/references/WORKTREE_PREFLIGHT.md` and complete it exactly.
2. Record the exact worktree path, branch, revision, dirty state, Python
   version, codebase-memory project identity, index status, node count, and
   edge count.
3. Read `references/pane-identity.md`, the current `tmux.py`, `sessions.py`,
   `agent_context.py`, relevant schemas, fake tmux fixture, and current tests.
4. Confirm the worktree is based on the clean master revision supplied with
   this pack. Stop if source or ownership contradicts the pack in a way that
   would overwrite newer architecture.

## Writable scope

Production and test writes are limited to the following paths unless a source
contradiction requires a narrowly documented equivalent:

```text
src/agent_workflow/tmux.py
src/agent_workflow/sessions.py
src/agent_workflow/agent_context.py
src/agent_workflow/state.py                 # only if persisted status needs an additive field
schemas/                                     # only schemas for changed persisted fields
tests/conftest.py
tests/acceptance/test_tmux_pane_identity_journey.py
tests/invariants/test_tmux_pane_identity.py
tests/live/test_live_adapters.py             # only the opt-in shared-window journey
docs/COMMAND_REFERENCE.md                    # only if a public diagnostic field/command changes
docs/OPERATIONS.md                           # only if operational recovery text changes
docs/MCP_SERVER.md                            # only if exposed status shape changes
```

The ticket may update its own handoff/evidence files. Do not modify prompt
packs, backlog state, provider adapters, model policy, worktree management,
receipt authority, or unrelated process-policy files.

## Required behavior

1. Shared-window launch captures and persists tmux `#{pane_id}` (for example
   `%112`) as the pane locator. It must not persist a pane index as the sole
   locator.
2. The pane is bound to the application run/session ID, and assignment ID if
   required, through tmux metadata or an equivalent verified mechanism.
3. `task-complete`, observe/status, interrupt, terminate, kill, and reusable
   candidate discovery use the stable locator/binding consistently.
4. Dedicated-session runs remain compatible and continue to use their session
   identity correctly.
5. Adding/removing/reordering other panes does not change which pane the run
   controls. A mismatch must fail closed rather than control another agent.
6. Actual pane destruction or tmux-server loss is reported as a genuine
   orphan/unavailable condition and follows existing recovery semantics. It is
   never silently rebound by name, PID, or pane position.
7. Existing positional status records receive a narrow safe compatibility
   path: upgrade only with an unambiguous run-bound pane, otherwise report the
   legacy target as unavailable and preserve evidence.
8. Keep status/diagnostic output truthful and additive where possible.

## Acceptance journeys

Add or update a black-box installed-product journey that launches an
interactive shared-window fixture, records the pane ID, changes pane layout,
and successfully completes the task against the original pane. The journey
must also prove that a destroyed pane is not rebound to another live pane.

Add a compact invariant matrix for:

- pane index changes with constant `%pane_id`;
- binding match, missing binding, and binding mismatch;
- legacy positional target with unambiguous versus ambiguous recovery;
- dedicated-session target compatibility;
- actual pane loss versus stale positional target.

Add or update an opt-in real-tmux journey when the host supports live tmux.
Keep it marked `live`; do not make the default suite depend on a running
interactive server.

## Security and authority constraints

- Pane identity is an execution-control boundary. Never accept a human name,
  caller-selected pane position, or stale status projection as authority.
- The durable run/session identity and verified pane binding must agree before
  sending keys or marking an agent reusable.
- Do not expose secrets or arbitrary terminal contents in new diagnostics.
- Preserve no-follow/path and sealed-evidence rules; no new mutable authority
  may be introduced.

## Validation

Run the focused installed/invariant journeys, shell syntax/compile checks as
appropriate, and the full test suite. Record exit codes and expected skips in
the completion report. Run:

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/tmux-pane-identity-reliability
pytest -q tests/acceptance/test_tmux_pane_identity_journey.py tests/invariants/test_tmux_pane_identity.py
pytest -q
```

Before handoff, refresh the exact worktree codebase-memory index and record
the final counts. Use `templates/TICKET_COMPLETION.md`, write strict
`completion.json`, run `agent-workflow agent task-complete` exactly once, and
exit the interactive executor cleanly so the runner can collect and seal the
run. Do not claim completion from terminal prose.

## Stop conditions

Stop and report blocked if:

- the current source has already changed the target identity model in a way
  not covered by this prompt;
- a legacy status cannot be upgraded without ambiguous pane ownership;
- a required installed/live journey cannot run and no honest fallback can
  prove the same contract;
- the implementation would require changing receipt authority, provider
  adapters, or unrelated messaging scope;
- pane capacity prevents interactive launch and the operator has not chosen a
  structured fallback.

## Required handoff

The handoff must list the exact changed paths, baseline/head revisions,
identity model, migration behavior, focused/full/live test commands with exit
codes, unresolved limitations, and the final sealed run/evaluation evidence.
