# Traffic-Light Status System for Agent Workflow

## Purpose

This kit defines a consistent visual language for progress updates, tmux status
rendering, popup/dashboard rows, and repository documentation.

The light is **derived operator-attention metadata**, not a new lifecycle state
and not an authoritative record.

| Light | Meaning | Required response |
|---|---|---|
| Green | Healthy, complete, or progressing normally | No operator action |
| Yellow | Review, acknowledgement, decision, retry, or possible stall | Inspect soon |
| Red | Blocked, failed, unsafe, orphaned, or terminal unavailable | Intervene now |
| Neutral | Queued, not started, archived, or insufficient live evidence | No live conclusion |

## Accessibility rule

Never communicate status by color alone. Every presentation must include at
least one additional signal:

- Green: circle plus `✓`, text `Healthy`
- Yellow: diamond plus `!`, text `Attention`
- Red: octagon plus `×`, text `Action required`
- Neutral: rounded outline plus `–`, text `No live signal`

For terminals, use a glyph and a label or count. For documents, use the supplied
SVG or PNG assets with alt text.

## Precedence

When multiple conditions exist, use:

`red > yellow > green > neutral`

Neutral applies only when there is no meaningful live health conclusion.
A queued run should not become green merely because no failure is recorded.

## Recommended derivation

### Red

Use red when any authoritative or observed condition indicates immediate
operator intervention, including:

- lifecycle `failed` or `blocked`;
- orphaned process/run binding;
- expected tmux terminal unavailable;
- explicit unsafe-to-continue or security violation;
- repeated recovery attempts exhausted.

### Yellow

Use yellow for non-terminal attention:

- review requested;
- acknowledgement required;
- maintainer decision required;
- retry in progress;
- possible stall;
- inbox item awaiting handling.

### Green

Use green only when the run is healthy or successfully terminal and no yellow
or red condition remains. Display the actual lifecycle text beside the light,
for example `✓ Healthy · running` or `✓ Healthy · completed`.

### Neutral

Use neutral for queued, not-started, archived, or unknown items where a current
health claim would be misleading.

## Integration order

1. Add a pure attention-derivation module and unit tests.
2. Extend the operator snapshot with `attention`, `label`, and `reasons`.
3. Generate a bounded, atomic cache for status-line reads.
4. Render lights in the popup and dedicated dashboard.
5. Add the opt-in tmux status-line fragment.
6. Add README/docs assets and accessibility checks.
7. Add real-tmux acceptance coverage.
8. Keep embedded sidebars optional and gated behind the dedicated UI-pane role.

## tmux status line

Install the example script:

```bash
install -Dm755 examples/tmux/tmux-status-line.sh \
  "${HOME}/.local/lib/agent-workflow/tmux-status-line.sh"
```

Source the opt-in configuration:

```tmux
source-file /path/to/examples/tmux/agent-workflow-traffic-light.conf
```

The production status-line command must read a precomputed cache. It must not
walk every run directory or make one tmux call per pane during each repaint.

Suggested output:

```text
●4 ◆2 ◆1 ○3
```

The actual configuration colors and shapes differentiate green, yellow, red,
and neutral. A verbose mode may render:

```text
✓ 4 healthy  ! 2 attention  × 1 blocked  – 3 inactive
```

## Popup and dashboard row

Recommended row format:

```text
× Action required  RUN-1042  failed           %17  test-agent
! Attention        RUN-1049  awaiting_review  %21  docs-agent
✓ Healthy          RUN-1051  running          %24  implementation-agent
– No live signal   RUN-1055  queued             —  validation-agent
```

Do not hide the lifecycle status behind the light. The light answers “how
urgently should the operator look?” while lifecycle status answers “what state
is the run in?”

## Progress updates in ChatGPT or operator reports

Use this exact convention:

```markdown
🟢 Complete / healthy
🟡 In progress / review or risk identified
🔴 Blocked / failed
⚪ Not started / no live signal
```

Example:

```markdown
🟢 Snapshot contract and tests complete.
🟡 Popup rendering is implemented; real-tmux acceptance remains.
🔴 Status cache refresh is blocked by an unresolved pane-identity regression.
⚪ Embedded sidebar is intentionally deferred pending maintainer approval.
```

## Asset usage

Use SVG for README and generated documentation whenever supported. Use PNG for
surfaces that cannot render SVG.

Examples:

```markdown
![Healthy](assets/status/traffic-green.svg)
![Attention](assets/status/traffic-yellow.svg)
![Action required](assets/status/traffic-red.svg)
![No live signal](assets/status/traffic-neutral.svg)
```

The `traffic-light-reference-generated.png` file is decorative only. Do not use
it as the functional status icon because it lacks compact labels and
color-independent shapes.

## Architectural guardrails

- Durable run, lifecycle, review, inbox, and tmux-observation records remain
  authoritative.
- The color is recomputed and disposable.
- UI actions call lifecycle services; they do not edit status files or directly
  kill tmux resources.
- Pane identity uses stable `%pane_id` and `@agent-workflow-*` metadata.
- UI panes use a dedicated role and are excluded from agent capacity/layout
  calculations.
- Cache writes are atomic and bounded.
- Status rendering fails neutral, not green.
- Missing evidence must never be interpreted as healthy.
