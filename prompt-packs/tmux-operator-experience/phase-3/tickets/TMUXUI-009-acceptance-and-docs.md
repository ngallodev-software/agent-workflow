# TMUXUI-009 — installed acceptance, security, documentation, and release integration

**Backlog:** [`TMUXUI-009`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-005, TMUXUI-006, TMUXUI-007

## Goal

Close the core tmux operator experience as a truthful installed product with deterministic fake-tmux evidence, opt-in real tmux/fzf evidence, adversarial coverage, package-data validation, complete user documentation, uninstall proof, and release-drift checks.

## Writable paths

- Installed-product and opt-in live acceptance tests/fixtures.
- Compact security/invariant tests only where existing coverage is insufficient.
- Packaging metadata/assets and documented supported capability boundaries.
- `README.md`, command reference, installation, operations, testing, config example/schema, man/help content, changelog, and authoritative tmux operator docs as behavior requires.
- Phase evidence artifacts permitted by repository conventions.

Do not add new feature scope, embedded sidebar, broad compatibility claims, or source-only test substitutes.

## Required behavior and evidence

- Build a clean wheel and install into an isolated environment.
- Execute snapshot, status cache/render, popup selector/focus/preview, lifecycle action, dashboard, refresh, install, and uninstall journeys through installed commands/assets.
- Use deterministic fake tmux for CI coverage and an opt-in real tmux/fzf journey for actual popup/window/layout behavior.
- Live journey changes pane layout/indexes, verifies stable focus, destroys a pane and verifies unavailable/no rebind, exercises one confirmed action, and cleans all UI resources.
- Test ANSI/OSC injection, oversized/binary preview, stale selection, malformed/symlink cache, unavailable tmux/fzf, conflicting config, concurrent refresh, and cancellation.
- Record exact tmux/fzf/Python/platform versions, commands, exit codes, skips, and cleanup.
- Document that broad platform support remains governed by REL-003.
- Run focused/full tests as repository policy requires, `python3 scripts/audit-release-assets.py`, prompt-pack validation, release checks, and sealed handoff collection.

## Acceptance

The feature is not complete until installed commands and packaged assets pass. README remains concise and links to authoritative docs. Uninstall leaves no namespaced hooks/options/windows/workers/cache claimed as active. Every limitation is explicit.

## Stop conditions

Stop rather than claiming completion if live tmux cannot be exercised, package assets are absent from the wheel, uninstall is incomplete, security cases fail, or docs describe unimplemented behavior. Use `templates/TICKET_COMPLETION.md`.
