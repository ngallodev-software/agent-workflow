# Codex execution prompt — comparative benchmark real-host acceptance

You are receiving the complete `agent-workflow` 0.7.9 release-candidate source after checkpoint 10. Your task is to execute the remaining real-host benchmark gates, repair only defects revealed by those gates, and return a complete evidence-backed acceptance or rejection.

## Authority and baseline

Read, in order:

1. repository `AGENTS.md`;
2. `docs/BACKLOG.md`;
3. `docs/BENCHMARK_ENHANCEMENTS_CHECKPOINT_10_RELEASE_CANDIDATE_REVIEW.md`;
4. this pack's `EXECUTION_PROTOCOL.md`;
5. `EVALUATION_PLAN.md`;
6. each phase manifest and ticket before executing that phase.

Treat checkpoint 10 as the implementation baseline. The remaining claims are unverified external gates, not assumed defects. Do not rewrite architecture before collecting real-host evidence.

## Operating constraints

- Work from a real Linux, WSL2, or macOS host with tmux.
- Launch benchmark runs from an existing tmux pane with room for exactly two additional panes.
- Use authenticated subscription sessions by default. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` must be absent for subscription-profile runs.
- Use isolated virtual environments and disposable benchmark fixture/worktree roots.
- Preserve raw evidence. Never edit generated run evidence to make a gate pass.
- Do not expose credentials, provider session files, environment secrets, or private review mappings in the public evidence bundle.
- Keep Codex, Claude, full-suite, and fast-suite cohorts separate.
- Do not downgrade a failed task, harness, browser, timing, or guardrail check into a warning.
- Do not change evaluator weights, time limits, or required checks after beginning a run.

## Required execution

### 1. Establish a trustworthy baseline

Validate the transferred archive/checksum, create a clean baseline commit if the archive has no `.git`, install the candidate outside the source checkout, run the deterministic local gates, validate this pack, and record all versions and digests.

### 2. Execute real compact runs for both subscription providers

Run `priority-picker-fast-v1` once with `codex-subscription.json` and once with `claude-subscription.json`, using the development policy. For each provider:

- capture tmux before launch;
- start continuous pane monitoring before `benchmark run`;
- prove exactly two additional panes are created in the invoking window;
- prove no detached benchmark session is created;
- prove both pane contents change while the provider is running;
- prove the same pane IDs remain bound to their arm through completion;
- prove each arm's model phase is below 150 seconds and the paired model critical path is below 180 seconds;
- prove provider usage evidence is present and truthful for the selected executor;
- prove the automated pipeline reaches `awaiting_human_review` with both live applications ready.

A provider unavailable due to missing subscription/authentication leaves the handoff blocked. Do not silently substitute an API profile.

### 3. Exercise a real multi-phase full benchmark

Run one development-policy `priority-picker-v2` benchmark with an authenticated subscription executor. Prove the two pane IDs are reused through all three model phases and the panes remain the only benchmark arm panes in the invoking window.

### 4. Exercise cancellation and no-orphan behavior

Use a disposable real-provider trial. Capture the pane's process group and descendants, terminate/replace the owned pane helper during active provider work, and prove every pre-termination descendant exits. Verify the coordinator records infrastructure failure and only the preplanned fresh paired retry may proceed. Preserve before/after process snapshots and event evidence.

### 5. Inspect preserved applications and complete blinded reviews

For each compact provider run:

- confirm both live URLs remain reachable after scoring/report generation;
- inspect search, filters, sorting, detail interaction, export, keyboard use, focus, responsive states, empty/invalid states, and console errors in a real browser;
- verify generated visual/accessibility evidence exists and corresponds to the live URL;
- prepare blinded assignments that contain only left/right labels and no treatment names;
- obtain the configured minimum independent human review count for the development claim (one reviewer per run), with a second reviewer strongly preferred for the release-candidate decision;
- submit reviews, regenerate reports, and run `benchmark verify`.

The agent performing implementation or orchestration may not be the sole independent final gate reviewer.

### 6. Exercise lifecycle and cleanup

Prove:

- default cleanup preserves live applications and arm worktrees;
- `live-stop` reports all processes stopped;
- `live-start` restores both applications and keeps the blinded mapping stable;
- explicit `cleanup --stop-live-apps --remove-worktrees` closes only panes still owned by the run and removes arm worktrees only after all live processes are gone;
- repeated stop/cleanup commands are safe and truthful;
- the coordinator and sealed run evidence remain verifiable after cleanup.

### 7. Evaluate and decide

Complete `handoff-evidence/eval-results.json`, then run:

```bash
python prompt-packs/benchmark-real-host-release-candidate-gate/evals/evaluate_handoff.py \
  --evidence-root handoff-evidence \
  --results handoff-evidence/eval-results.json \
  --output-dir handoff-evidence/final-evaluation
```

The final independent reviewer must inspect the raw evidence and implementation diff, then write `handoff-evidence/final-gate-review.md` from the supplied template. A valid acceptance requires:

- every mandatory evaluation check is `pass`;
- score is exactly 100/100;
- no unresolved critical/high defect;
- independent gate decision is `accept`;
- source/package/run evidence hashes verify.

## Repair policy

When a real-host gate exposes a defect:

1. preserve the failed run and evidence unchanged;
2. classify implementation defect, harness defect, host/configuration defect, or provider outage;
3. for implementation/harness defects, create a narrow failing regression test first where practical;
4. make the smallest cohesive correction;
5. update all affected docs/help/man/source-package mirrors;
6. rerun local gates and the failed real-host gate from fresh worktrees;
7. record the old and new evidence lineage;
8. do not erase the original failure.

Stop and report `blocked` rather than guessing when authentication, paid access, browser/runtime identity, or independent reviewers are unavailable.

## Final return

Return one archive containing:

- the complete corrected source;
- this prompt pack;
- `handoff-evidence/` with raw and evaluated evidence;
- an exact changed-file manifest and SHA-256 file;
- a concise final report stating accepted, rejected, or blocked and naming every remaining gate.
