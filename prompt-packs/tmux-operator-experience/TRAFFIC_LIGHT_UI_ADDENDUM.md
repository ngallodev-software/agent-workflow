# Traffic-Light UI Addendum Prompt

Implement the traffic-light operator-attention presentation layer for the
Agent Workflow tmux operator experience.

## Authority boundary

The light is derived presentation metadata. Do not create a second lifecycle
state machine. Durable run, workflow, inbox, review, and tmux-observation
records remain authoritative.

## Required semantics

- Red: immediate operator action.
- Yellow: review or monitoring needed.
- Green: healthy or successful with no outstanding attention.
- Neutral: no reliable live health conclusion.
- Precedence: red, then yellow, then green, then neutral.
- Missing evidence fails neutral, never green.

Every rendering must include a non-color signal: glyph/shape plus text or
count. Preserve the underlying lifecycle status alongside the light.

## Required implementation

1. Pure deterministic derivation function with reasons.
2. Versioned snapshot fields matching
   `schemas/operator-attention-v1.schema.json`.
3. Atomic bounded summary cache.
4. Popup and dashboard rendering.
5. Opt-in tmux status-line command.
6. SVG/PNG documentation assets.
7. Unit, fake-tmux, real-tmux, `NO_COLOR`, and accessibility tests.
8. Installation, removal, and operational documentation.

## Prohibited implementation

- Storing a color as authoritative lifecycle state.
- Inferring green from missing data.
- Per-pane or per-run subprocess calls during status repaint.
- Direct destructive tmux actions from the presentation layer.
- Automatic mutation of global user keybindings or tmux options.
- Color-only status communication.

## Completion evidence

Report changed files, tests, real-tmux evidence, snapshot/cache examples,
accessibility checks, documentation link validation, and any unresolved
limitations. Do not mark complete without real-tmux acceptance evidence.
