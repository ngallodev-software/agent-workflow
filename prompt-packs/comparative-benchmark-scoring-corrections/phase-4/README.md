# Phase 4 — observable execution, durable review, and fast benchmark

## Objective

Make comparative runs directly observable in the operator's current tmux window, preserve both built applications for human assessment, and provide a compact end-to-end suite whose model-execution critical path is strictly less than three minutes.

## Ordering

1. establish the stable two-pane execution contract;
2. add the live-review process lifecycle on those same panes;
3. add and calibrate the compact suite against the corrected scoring contract;
4. independently review installed behavior and cleanup safety.

## Exit gate

The gate must exercise an installed build from inside tmux. Static mocks alone cannot accept the pane topology or process-survival requirements. The fast suite must retain paired isolation, full scoring, visual evidence, blinded review, and provenance; only task scope and model phase count may be reduced.
