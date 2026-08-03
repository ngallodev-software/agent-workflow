# Benchmark enhancements checkpoint 07 validation

Date: 2026-08-02  
Parent: checkpoint 06

## Scope

Checkpoint 07 adds executable timing evidence for `priority-picker-fast-v1` and re-runs the benchmark/release contract partition. It does not claim that a real Codex or Claude subscription run has been measured on this host because tmux and authenticated provider sessions are unavailable here.

## Fast-suite calibration

The new invariant launches the compact suite's two synthetic arms concurrently against independent copies of the starter fixture. Each arm:

- executes the same single `build-verify` phase used by the benchmark;
- runs the fixture's public tests;
- writes provider-style usage evidence;
- must exit successfully before the suite's 150-second phase timeout.

The paired critical-path measurement must remain below 180 seconds. This catches accidental fixture growth, serial execution, executor breakage, missing usage evidence, and drift between the stated wall-time contract and the executable compact task.

Command:

```bash
python -m pytest -q tests/invariants/test_benchmark_operator_experience.py
```

Result:

```text
9 passed in 9.11s
```

## Release and benchmark contract partition

The benchmark contracts, operating policy, operator experience, release evidence, distribution, documentation synchronization, and installer tests produced 50 passing assertions. The grouped command printed a complete passing result, although the process did not terminate cleanly under the outer execution wrapper. Running the constituent modules independently confirmed clean exits; no assertion regression was found.

## Remaining external gates

The following evidence still requires an installed interactive host:

- real tmux confirmation that exactly two panes are added to the invoking window;
- live Codex and Claude subscription timing for the compact task;
- visible provider stdout/stderr in both panes;
- live application preservation through blinded human scoring;
- Playwright/Chromium visual capture against the preserved applications;
- explicit live-stop and destructive cleanup verification.

Checkpoint 07 therefore strengthens deterministic development evidence without converting unavailable external evidence into a release claim.
