# feature-modularization

Implement DEC-009 without changing authority semantics: split oversized modules behind stable facades, add the minimal trusted entry-point plugin host, then evaluate one evidence-backed subsystem extraction only after real first-party plugin use.

## Current implementation state

0.7.7 contains the process-policy decomposition slice and the trusted plugin command-host foundation. PLUG-001 remains in progress only for bounded installed package-resource activation and independent MOD-GATE-1 review. Agents must extend the existing host rather than create a competing registry.

## Critical path

`MAINT-001` → `MOD-GATE-0` → `PLUG-001` → `MOD-GATE-1` → `ARC-004` → `MOD-GATE-2`

`ARC-004` remains blocked in the canonical backlog until the first-party spec plugin supplies stable real-world evidence. Its prompt is planning/review authority, not permission to split repositories early.

## Steering rules

- Preserve immutable authority, evidence formats, command behavior, and installed-product journeys.
- Prefer package-level feature boundaries and compatibility facades over deletion.
- Keep built-in features explicitly enabled when they alter topology or authority.
- Use standard Python entry points and a small typed atomic registry; do not add Pluggy until ordered 1:N hooks are demonstrated.
- Never combine a behavior-preserving module split with new feature semantics in the same ticket.
