# Comparative benchmark operations

## Built-in suites

The 0.7.9 source ships three built-in suites:

| Suite | Use | Model phases | Scoring semantics |
|---|---|---:|---|
| `priority-picker-v1` | Historical compatibility and old-receipt verification | 3 | Frozen legacy evaluator semantics |
| `priority-picker-v2` | Full corrected comparative benchmark | 3 | Explicit versioned per-check contract totaling 100 |
| `priority-picker-fast-v1` | Compact development comparison | 1, hard-capped at 150 seconds | Same corrected 100-point contract and review lifecycle |

Do not combine full, fast, or legacy cohorts in one winner calculation. Their benchmark identities and task scopes differ. The fast-suite timing claim applies only to the model-execution critical path; browser capture, deterministic scoring, report generation, and human assessment are measured separately.

Subscription-backed Codex or Claude CLI sessions are the default. API-key profiles remain optional and explicit.

## Export and validate a suite

```bash
agent-workflow benchmark suite-export /tmp/priority-picker-v2 \
  --benchmark-id priority-picker-v2

agent-workflow benchmark suite-export /tmp/priority-picker-fast-v1 \
  --benchmark-id priority-picker-fast-v1

agent-workflow benchmark validate \
  /tmp/priority-picker-fast-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-fast-v1/executors/codex-subscription.json
```

The release audit requires every packaged suite to have the same file inventory and bytes as its authoring source under `benchmarks/specs/`.

## Authenticate and check readiness

Authenticate with the provider CLI outside the benchmark, then run the read-only checks:

```bash
agent-workflow benchmark auth-check \
  /tmp/priority-picker-fast-v1/executors/codex-subscription.json

agent-workflow benchmark readiness \
  /tmp/priority-picker-fast-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-fast-v1/executors/codex-subscription.json \
  --policy /tmp/priority-picker-fast-v1/policies/development.json
```

A subscription profile fails when the corresponding API credential is present in the environment. Unset it or deliberately select the API profile. Readiness checks provider authentication, visual-runtime identity, policy thresholds, paired retry isolation, and tmux availability without creating worktrees.

## Create the fixture and run plan

```bash
agent-workflow benchmark fixture-create \
  /tmp/priority-picker-fast-v1/benchmark-spec.json \
  /tmp/priority-picker-fast-fixture

agent-workflow benchmark plan \
  /tmp/priority-picker-fast-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-fast-v1/executors/codex-subscription.json \
  --policy /tmp/priority-picker-fast-v1/policies/development.json \
  --repo /tmp/priority-picker-fast-fixture \
  --run-id priority-picker-fast-smoke
```

Planning creates the coordinator and paired arm worktrees and seals their task, treatment, executor, policy, fixture, and runtime identities.

## Run from inside tmux

`benchmark run` must be invoked from an existing tmux pane:

```bash
tmux new-session -A -s benchmark-operator
agent-workflow benchmark run priority-picker-fast-smoke
```

At launch, the runner:

1. resolves the invoking tmux window;
2. preflights room for both arm panes before changing the layout; `benchmark readiness` exposes the same non-mutating capacity result before planning;
3. creates exactly two additional panes in that same window—one for `control_raw`, one for `workflow_full`;
4. keeps the command pane focused;
5. reuses the two stable pane IDs across phases and retries;
6. streams provider stdout and stderr visibly while writing bounded evidence logs.

The provider runs in its own process group. Replacing, interrupting, or terminating the foreground pane helper forwards termination to the provider so a model process is not left orphaned.

The automated pipeline executes the paired task, starts live applications, captures browser evidence from those live URLs, scores, consolidates, and reports. It then enters `awaiting_human_review`; it does not shut down the applications. Live applications bind to `0.0.0.0` by default, receive distinct ephemeral ports per arm, and status displays a LAN-advertised URL. The host firewall still controls whether other machines can connect.

## Inspect live applications

```bash
agent-workflow benchmark status priority-picker-fast-smoke
```

Status includes the stable operator pane IDs and one runtime record per pair/arm with its LAN URL, local readiness URL, distinct port, PID, worktree, logs, and current lifecycle state. After model work, the same two arm panes remain open, display the current live-review URL and server output, and remain visible after the server exits for diagnosis.

Restore or stop the live applications explicitly:

```bash
agent-workflow benchmark live-start priority-picker-fast-smoke
agent-workflow benchmark live-stop priority-picker-fast-smoke
```

`live-start` is idempotent when every server is ready. A restart prefers the previous ports so already displayed URLs remain stable where possible. Partial startup state and failure details are preserved under the coordinator's `.agent-workflow-benchmark-runtime/<run-id>/` directory, outside sealed scoring evidence.

## Blinded human review

```bash
agent-workflow benchmark review \
  priority-picker-fast-smoke \
  --reviewer reviewer-01
```

The assignment exposes `left` and `right` evidence and live URLs, not `control_raw` or `workflow_full`. Reopening an existing assignment refreshes live URLs from the private label mapping without changing that mapping. Submit the completed template with `--input`, then render and verify:

```bash
agent-workflow benchmark review \
  priority-picker-fast-smoke \
  --reviewer reviewer-01 \
  --input completed-review.json

agent-workflow benchmark report priority-picker-fast-smoke
agent-workflow benchmark verify priority-picker-fast-smoke
```

Development, internal, and publication claims retain their configured reviewer-count and eligibility requirements.

## Cleanup is preservation-first

```bash
# Record cleanup state but preserve live apps and arm worktrees.
agent-workflow benchmark cleanup priority-picker-fast-smoke

# Stop apps, then remove verified arm worktrees explicitly.
agent-workflow benchmark cleanup priority-picker-fast-smoke \
  --stop-live-apps \
  --remove-worktrees
```

Default cleanup preserves both the reviewable applications and their worktrees. `--stop-live-apps` also closes the two benchmark-owned panes, but only after every server is confirmed stopped. If any process remains alive or cannot be signaled, the panes and worktrees are preserved for diagnosis and destructive cleanup fails. Destructive worktree cleanup also requires valid consolidated evidence. The coordinator worktree and `benchmarks/runs/<run-id>` evidence remain preserved.

## Optional API authentication

```bash
OPENAI_API_KEY=... agent-workflow benchmark readiness \
  /tmp/priority-picker-fast-v1/benchmark-spec.json \
  --executor /tmp/priority-picker-fast-v1/executors/codex-api-key.json \
  --policy /tmp/priority-picker-fast-v1/policies/development.json
```

Do not pool a subscription cohort with an API-key cohort. Authentication mode and billing semantics are sealed executor identity.

## Publication visual runtime

```bash
agent-workflow benchmark runtime-seal \
  /suite/visual-runtime-lock.json \
  /suite/visual-runtime-lock.publication.json \
  --container-image registry.example/agent-workflow-benchmark@sha256:<64-hex-digest>

agent-workflow benchmark runtime-attest \
  /suite/visual-runtime-lock.publication.json \
  --claim-level publication
```

Pass the sealed lock to readiness and planning through `--runtime-lock`. A mutable image tag, unresolved font, mismatched browser binary, or unverified host runtime fails publication readiness.

## Failure interpretation

- **Not inside tmux:** no model phase starts and no partial arm-pane layout is created.
- **Pane capacity failure:** both-pane preflight fails before either pane is added.
- **Authentication failure:** repair the selected provider session; do not silently switch billing paths.
- **Infrastructure failure:** only the preplanned fresh paired retry may run.
- **Task failure or low score:** terminal benchmark evidence; no task retry.
- **Live server failure:** partial lifecycle evidence and logs remain; automated completion records `failed_stage=live_review` and fails rather than substituting a static page.
- **Live teardown failure:** active processes, panes, and worktrees remain preserved; cleanup refuses destructive removal.
- **Pane evidence timeout:** the pane command is terminated before the arm is classified as an infrastructure failure, preventing an orphaned provider from overlapping a retry.
- **Missing provider usage:** remains null and may invalidate the configured guardrail.
- **Missing human review:** report remains `awaiting_human_review`; no final composite or winner.
