# Comparative benchmark implementation

The comparative benchmark is implemented behind the built-in `agent_workflow.benchmarking` package. Every run compares identical canonical task input in isolated `control_raw` and `workflow_full` worktrees. The two arms are released concurrently behind a barrier and remain separately evidenced through execution, browser capture, scoring, and blinded review.

## Built-in suite versions

- [`priority-picker-v1`](../benchmarks/specs/priority-picker-v1/) preserves historical v1 evaluator meaning and old receipt verification.
- [`priority-picker-v2`](../benchmarks/specs/priority-picker-v2/) is the full corrected task with an explicit versioned per-check scoring contract.
- [`priority-picker-fast-v1`](../benchmarks/specs/priority-picker-fast-v1/) is a compact corrected task with one model phase capped at 150 seconds.

Each suite is authored under `benchmarks/specs/` and mirrored byte-for-byte under `src/agent_workflow/assets/benchmarks/`. The release audit rejects missing, extra, or differing packaged files.

## What is implemented

- coordinator plus isolated arm Git worktrees from one frozen fixture revision;
- separate canonical-task, arm-wrapper, constraint-profile, and effective-prompt digests;
- exactly two stable benchmark panes added to the invoking tmux window, one per arm;
- visible provider stdout/stderr with bounded durable logs and atomic result handoff;
- pane/run/arm binding validation, up-front two-pane capacity checks, and provider process-group cancellation;
- phase-local process identity, token usage, cache fields, cost, latency, and timing;
- pair wall time, summed arm wall time, critical-path time, and measured start skew;
- legacy v1 scoring plus corrected versioned 100-point per-check contracts;
- strict rejection of missing, duplicate, unknown, over-awarded, or evidence-mismatched corrected checks;
- one preserved live application server per selected pair/arm worktree;
- Playwright/Chromium visual capture from the preserved live application at desktop, tablet, and mobile viewports;
- lifecycle status, explicit live start/stop, restart-safe ports where available, and partial startup failure records;
- blinded reviewer assignments copied into neutral `left` and `right` namespaces with live URLs and URL refresh;
- 70% machine / 30% human composite after the required reviews exist;
- digest-verified consolidation under `benchmarks/runs/<run-id>`;
- preservation-first cleanup and explicit stop/removal of verified arm worktrees;
- packaged suite export for installed-wheel use;
- subscription-session authentication preflight for Codex and Claude, with optional explicit API profiles and no silent fallback;
- versioned development, internal, and publication operating policies;
- infrastructure-only fresh-pair retry with every attempt retained;
- deterministic paired-bootstrap confidence intervals and policy-gated winner declarations;
- development runtime attestation plus publication runtime sealing from a content-addressed browser image.

## Operator topology and process lifecycle

`benchmark run` must start inside tmux. Before execution, the runner resolves the current window and verifies that both required panes fit. It then creates exactly two additional panes and records their stable IDs in the benchmark runtime directory. The invoking pane remains focused.

The same arm pane is respawned for every phase or retry. A small foreground helper launches the provider in a new process group, sends the phase prompt through standard input, mirrors provider output into the pane, writes bounded evidence files, and atomically publishes the terminal result. `SIGTERM`, `SIGINT`, and `SIGHUP` are forwarded to the provider process group.

This design keeps the operator surface observable without treating terminal capture as authoritative evidence.

## Live review lifecycle

After the selected arm attempts finish, the automated pipeline starts a server for every pair/arm worktree and waits for its declared readiness URL. By default each server binds to `0.0.0.0` on a distinct ephemeral port; runtime records contain the LAN-advertised URL, local readiness URL, bind host, port, PID, command, worktree, logs, and lifecycle timestamps. They live below:

```text
<coordinator>/.agent-workflow-benchmark-runtime/<run-id>/
```

That directory is operational state outside the sealed benchmark evidence tree. Browser capture uses the live URL, then scoring and consolidation proceed while the servers remain active. The final automated state is normally `awaiting_human_review`, and the two arm panes switch to URL/log displays with `remain-on-exit` enabled. Normal benchmark completion never kills these panes; `benchmark live-stop` or explicit cleanup with `--stop-live-apps` is the teardown authority. A host firewall may still be needed for LAN access.

`benchmark status`, `live-start`, and `live-stop` expose or manage this lifecycle. Existing blinded assignments refresh their live URLs from the private label mapping without changing treatment blinding.

## Development quick start

Install visual support and the pinned Chromium runtime:

```bash
python -m pip install -e '.[benchmark-visual]'
playwright install chromium
```

Export and plan the compact suite:

```bash
agent-workflow benchmark suite-export /tmp/priority-picker-fast-v1 \
  --benchmark-id priority-picker-fast-v1
agent-workflow benchmark fixture-create \
  /tmp/priority-picker-fast-v1/benchmark-spec.json \
  /tmp/priority-picker-fixture
agent-workflow benchmark plan \
  /tmp/priority-picker-fast-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-fast-v1/executors/synthetic.json \
  --repo /tmp/priority-picker-fixture \
  --run-id priority-picker-smoke
```

Run from inside an existing tmux pane:

```bash
tmux new-session -A -s benchmark-operator
agent-workflow benchmark run priority-picker-smoke
agent-workflow benchmark status priority-picker-smoke
```

Create and submit blinded review evidence:

```bash
agent-workflow benchmark review priority-picker-smoke --reviewer reviewer-01
agent-workflow benchmark review priority-picker-smoke \
  --reviewer reviewer-01 \
  --input /path/to/completed-review.json
agent-workflow benchmark report priority-picker-smoke
agent-workflow benchmark verify priority-picker-smoke
```

Preserve by default, or stop and remove explicitly. Explicit teardown closes benchmark-owned panes only after all live servers are confirmed stopped; otherwise panes and worktrees remain for diagnosis:

```bash
agent-workflow benchmark cleanup priority-picker-smoke
agent-workflow benchmark cleanup priority-picker-smoke \
  --stop-live-apps --remove-worktrees
```

## Authentication and operating profiles

Real runs default to an existing provider CLI subscription session. `benchmark auth-check` verifies the selected session before any worktree is created and stores only bounded status evidence and output digests. Subscription profiles reject ambient API-key/access-token variables so a run cannot silently switch to metered API billing. Optional API profiles are separate executor configurations and therefore separate cohorts.

The suites include `development`, `internal`, and `publication` policies. They seal repetitions, retry semantics, cache treatment, assistance cohort, allowed authentication modes, confidence level, effect threshold, regression limits, and reviewer requirements. Use `benchmark readiness` before planning. See [DEC-002](DECISIONS/DEC-002-COMPARATIVE-BENCHMARK-OPERATING-POLICY.md) and the [operations guide](COMPARATIVE_BENCHMARK_OPERATIONS.md).

## Executor adapter contract

A real executor is supplied through `agent-workflow/benchmark-executor-config/v1`. Its argv template may use:

```text
{run_id} {benchmark_id} {pair_id} {case_id} {repetition}
{pair_nonce} {arm} {slot} {phase_id} {worktree} {stage_dir}
{phase_dir} {prompt_file} {usage_file} {suite} {run_dir}
```

The process runs with the arm worktree as its current directory. The same values are also exposed through bounded `AGENT_WORKFLOW_BENCHMARK_*` environment variables. The executor must consume `{prompt_file}`, perform only the current phase, and leave task changes in `{worktree}`.

For complete efficiency evidence, write JSON to `{usage_file}` containing the versioned usage fields. Unknown values remain `null`; they are never converted to zero. A required provider-usage guardrail invalidates the score when complete usage was required but not supplied.

## Timing semantics

The report preserves distinct timing categories:

- each phase: wall, active process, provider elapsed, first-output latency, queue wait;
- each arm: summed phase wall, active process, visual capture, machine verification, and measured non-human total;
- each pair: concurrent pair wall, sum of arm walls, critical path, and start skew;
- each run: execution, live startup, visual, machine scoring, consolidation, reporting, and automated-pipeline wall time;
- human review: reviewer-reported active review time.

The fast suite's under-three-minute contract applies only to its one model phase (`150 < 180` seconds). It does not conceal post-model automated or human work.

## Guardrails and claim levels

Required guardrails cover paired identity, declared treatment, start skew, writable scope, assistance cohort, visual capture, provider usage, and harness integrity. A failed required guardrail produces an invalid trial rather than a reduced score.

Synthetic executors and host-detected browser capture support development evidence only. Internal and publication profiles reject synthetic authentication. Publication readiness requires a runtime lock sealed from inside a content-addressed browser image with verified browser and font digests.

Do not combine legacy, full corrected, and compact cohorts. Benchmark ID, task version, scoring contract, evaluator, fixture, policy, executor, and runtime identities define comparability.

## Modular boundary

All authority-bearing orchestration and processing remains under `src/agent_workflow/benchmarking/`, with thin CLI parser/handler surfaces. The feature depends on narrow existing ports for contracts, subprocesses, tmux, Git worktrees, atomic files, and hashes. No benchmark-specific plugin registry or scorer hook was added.

The implementation and corrective sequencing are documented in the [owned prompt pack](../prompt-packs/comparative-benchmark-scoring-corrections/). The installed real-tmux/live-browser acceptance gate and first real subscription-backed timing cohort remain external evidence tasks.
