# ChatGPT Handoff Prompt — tmux Operator Experience

Execute the `tmux-operator-experience` prompt pack against the current `agent-workflow` repository.

## First decision

Read `docs/BACKLOG.md`. If PROC-006 is not accepted, do not implement TMUXUI-001 or later tickets. Instead verify the pack, report the exact blocking evidence, and stop without changing implementation files.

Do not execute TMUXUI-008 unless TMUXUI-GATE-001 is accepted and the maintainer has explicitly authorized the `needs-decision` backlog item.

## Execution

1. Read the pack README, execution protocol, delegation runbook, recommendation, backlog sequence, and prior-art analysis.
2. Validate the pack and exact source baseline.
3. Execute phases and dependency edges exactly as declared.
4. Use separate worktrees and named sessions for parallel tickets.
5. Independently review every handoff before integration.
6. Run installed-product journeys and the opt-in live tmux journey where the phase requires them.
7. Run the release drift audit and independent gates.
8. Update `docs/BACKLOG.md` states only when evidence justifies the transition.

## Non-negotiable architecture

- `agent-workflow` durable state and services are authoritative.
- The UI snapshot/cache is derived and disposable.
- Stable pane ID is the only managed pane identity.
- No imported shell status model, process-heuristic managed identity, global tmux mutation, or direct destructive UI command is allowed.
- Core acceptance is popup/status/dashboard; embedded sidebar is optional and separately gated.

Produce exact completion reports, integrated revision identifiers, test commands and exit codes, unresolved limitations, and explicit gate decisions.
