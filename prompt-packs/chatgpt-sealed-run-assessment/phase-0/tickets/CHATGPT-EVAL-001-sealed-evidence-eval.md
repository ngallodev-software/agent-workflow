# CHATGPT-EVAL-001 — sealed-run evaluation update

Backlog: `CHATGPT-EVAL-001`  
Dependencies: sealed foundation/hook run evidence in `references/sealed-runs/`  
Writable scope: evaluation contracts/collectors/scorers/reports, focused evaluation tests, this ticket's evidence notes, and necessary docs.  
Non-targets: HARD/MSG runtime implementation, host configuration, backlog status of existing HARD/MSG items, and fabricated scores.

## Acceptance

- Inspect all six sealed completion and final-receipt pairs.
- Identify the exact reason the ledger has zero rows and why eval collection has no score set.
- Add or update evaluation-system behavior only for demonstrated contract gaps.
- Add focused tests protecting missing-evaluation-plan, incomplete-score-set, sealed-receipt, and unavailable-environment semantics.
- Run the smallest relevant installed-product/invariant gates and release drift audit.
- Write truthful completion JSON/Markdown with hashes/paths and unresolved limitations.
