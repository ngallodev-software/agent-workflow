# Priority-picker visual regression fixture — blocked gate

The Phase 3 fixture is intentionally not represented as complete in this source archive.
The ticket requires a pinned offline browser image, pinned fonts, deterministic screenshot
comparison, and imported browser/Inspect artifacts before sealing. This environment does
not contain an authoritative browser image digest or a verified Inspect/browser evidence
bridge. Implementing an unpinned browser test would violate the ticket's stop condition.

The required protocol contract is frozen here for the follow-on implementation:

1. `child_started`
2. `child_request`
3. `child_result`
4. `child_finished`

All four records must be explicit, ordered, session-bound, and sealed. DOM and ARIA
assertions are primary; screenshots are secondary with a declared tolerance. Negative
fixtures must independently reject missing child telemetry, late/invalid results, ignored
results, broken Escape behavior, visual mismatch, and scope escape.
