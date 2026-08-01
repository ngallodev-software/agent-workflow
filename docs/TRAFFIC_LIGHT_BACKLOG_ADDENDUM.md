# Traffic-Light UI Backlog Addendum

This addendum is intended for the `tmux-operator-experience` prompt pack.

## Execution order

### TLUI-001 — Attention semantics and contract
**Priority:** P0  
**Depends on:** TMUXUI-001 snapshot contract

- Implement the pure derivation function.
- Add red/yellow/green/neutral precedence tests.
- Record reasons and lifecycle text separately.
- Validate against `operator-attention-v1.schema.json`.

**Acceptance:** missing evidence never resolves to green; red always outranks
yellow; presentation state is not persisted as lifecycle authority.

### TLUI-002 — Snapshot and cache projection
**Priority:** P0  
**Depends on:** TLUI-001

- Add attention fields to the operator snapshot.
- Produce one atomic bounded summary cache.
- Include schema/version and observed timestamp.
- Ensure repaint reads do not enumerate runs or panes.

### TLUI-003 — Popup and dashboard rendering
**Priority:** P1  
**Depends on:** TLUI-002, TMUXUI-003, TMUXUI-006

- Render glyph, label, lifecycle, run ID, and stable pane ID.
- Sort by red, yellow, green, neutral; preserve deterministic tie-breaking.
- Add current-pane highlighting without replacing attention state.
- Add monochrome and `NO_COLOR` behavior.

### TLUI-004 — Opt-in tmux status line
**Priority:** P1  
**Depends on:** TLUI-002, TMUXUI-002, TMUXUI-004

- Read only the snapshot/cache.
- Add compact and verbose modes.
- Document explicit installation and removal.
- Avoid automatic global tmux mutation.

### TLUI-005 — Documentation assets and accessibility
**Priority:** P1  
**Depends on:** TLUI-001

- Add SVG/PNG assets.
- Add alt text and color-independent shapes.
- Add light/dark legends.
- Document state semantics and examples.

### TLUI-GATE-001 — Independent acceptance
**Priority:** Gate  
**Depends on:** TLUI-001 through TLUI-005

- Unit tests for all precedence combinations.
- Fake-tmux tests for deterministic rendering.
- Real-tmux acceptance for status and popup.
- Verify terminal output under color, `NO_COLOR`, and monochrome conditions.
- Verify documentation links and packaged assets.
