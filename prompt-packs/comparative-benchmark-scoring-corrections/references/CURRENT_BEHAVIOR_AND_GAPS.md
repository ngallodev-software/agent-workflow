# Current 0.7.9 benchmark behavior and correction targets

## Current task

The built-in `priority-picker-v1` benchmark asks both arms to build a dependency-free Priority Picker application that validates backlog data, applies the frozen priority formula, ranks deterministically, offers search/filter/sort/detail/export behavior, and renders a polished responsive interface.

The suite is authored in `benchmarks/specs/priority-picker-v1/` and mirrored for installed export in `src/agent_workflow/assets/benchmarks/priority-picker-v1/`.

## Current identities

- benchmark ID: `priority-picker-v1`;
- `benchmark-spec.json` version: `1.1.0`;
- matrix-declared frozen version: `1.0.0`;
- control profile: `control-raw/v1`;
- workflow profile: `workflow-full/v1`;
- scorer IDs: `hidden-functional-v1`, `public-regression-v1`, `robustness-v1`, `accessibility-ui-v1`, `scope-completeness-v1`, and `engineering-quality-v1`.

The specification/matrix version mismatch is itself a correction target. Do not normalize it by editing historical v1 files.

## Current machine dimensions

- hidden functional: 45;
- public regression: 15;
- robustness: 10;
- accessibility/deterministic UI: 10;
- scope/completeness: 10;
- engineering quality: 10.

`evaluation/evaluate.py::outcome` equal-shares each dimension maximum across its returned checks.

## Current hidden checks

Nine equal checks cover one formula example, ID tie-break, attached score, title search, status filter, risk filter, title sort, ranked export, and fixture load. Each passing check effectively earns 5 points.

## Current public and engineering interaction

The public suite is one all-or-nothing 15-point check. Engineering quality calls the same public test result again as one of five equal two-point checks. The current contract does not explain whether that duplicate signal is intentional.

## Current browser groups

`capture_visual.py` records runtime match, app load, labels, one main landmark, export-control presence, focus movement, Enter-driven details, no console errors, and no overflow at three viewports. The accessibility scorer groups these into five all-or-nothing two-point groups.

The `focus-visible` name currently proves focus movement, not computed visible focus indication. The export check proves a labeled control exists, not that a correct JSON download occurs.

## Confirmed discrepancies

1. Named hidden allocations in the frozen matrix total 43 rather than 45.
2. Named accessibility allocations total 14 rather than 10.
3. The spec says `1.1.0`; the matrix says `1.0.0`.
4. The formula earns 5 implemented points, not the matrix's stated 10.
5. Validation coverage is narrower than the stated data contract.
6. Browser evaluation does not comprehensively exercise search/filter/sort/export, empty/invalid states, visible focus, or broader accessibility semantics.
7. The public suite is one all-or-nothing 15-point check.
8. Public-test success is counted again as a two-point engineering check.
9. Requirement matrix, evaluator, built-in scoring code, schemas, source suite, installed mirror, docs, and man page can drift independently.
10. The plugin API has no benchmark evaluator hooks; adding one only for this correction would violate the current feature boundary.

## Corrective principle

Preserve v1 exactly. Create a new major benchmark version with an exact machine-readable contract, explicit weights, richer evidence, calibration fixtures, version-aware comparison, source/package parity, generated or validated derivative documentation, and no dependency on an enabled plugin.
