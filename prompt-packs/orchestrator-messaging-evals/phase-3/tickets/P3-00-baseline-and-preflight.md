# P3-00 — Visual orchestration-child regression eval

## Objective

Build a tiny priority-picker web UI eval in a pinned offline browser container.
The parent must produce explicit child telemetry (`child_started`, request,
result, `child_finished`) before implementation/verification proceeds.

## Required behavior

- Fixed 1280x720 viewport, pinned browser/fonts, disabled animation, click and
  Escape paths, ARIA assertions, deterministic screenshot tolerance, and DOM
  assertions as the primary judge.
- Copy or manifest Inspect/browser transcript, screenshot, test report, and
  telemetry inside the run before sealing. A model transcript alone is not
  child-handoff proof.
- Negative fixtures fail for no child, late/invalid child result, ignored child
  result, broken Escape, visual mismatch, and scope escape.

## Writable paths

The new pinned UI fixture, Inspect evidence bridge, sealed telemetry/metrics
interfaces, matching tests, and documentation only.

## Acceptance criteria

Pinned functional and accessibility tests pass only with valid child telemetry;
the browser evidence is present in the final receipt; every listed negative
fixture fails for its intended reason.

## Tests

Run offline functional/ARIA/screenshot tests plus negative protocol and receipt
verification tests; record image/browser/font versions in evidence.

## Stop

If browser/image versions cannot be pinned or evidence cannot enter the final
receipt before sealing, deliver fixture design and a blocked gate report only.
