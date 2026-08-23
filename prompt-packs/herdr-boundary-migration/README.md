# herdr-boundary-migration

Move terminal/tmux/pane ownership to Herdr and expose the retained durable
agent-workflow capabilities through a first-party `herdr-agent-workflow` plugin.

Critical path: `HERDR-001 → HERDR-GATE-0 → HERDR-002 → HERDR-GATE-1 → HERDR-003 → HERDR-GATE-2 → HERDR-004 → HERDR-GATE-3`.

The inventory gate is mandatory. No implementation ticket may delete or move
code until it has exact symbol ownership, current-tree baselines, verified
Herdr API references, and disjoint writable paths.
