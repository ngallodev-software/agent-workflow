# MCP adapter plan

## Decision

Add an **optional, local stdio MCP adapter** after the 0.1 release work is
stable. Keep `agent-workflow` terminal-first: MCP is another local client of
the existing Python services, not the primary control plane, a daemon, an HTTP
API, or a remote-execution feature.

The fit is strong: the project already has typed command inputs, JSON-capable
output, durable run state, sealed receipts, and explicit lifecycle operations.
An adapter lets a coding client discover structured operations instead of
reconstructing shell syntax or parsing terminal tables.

## Goals and non-goals

| Goals | Non-goals |
|---|---|
| Inspect local workflow health, runs, packs, and sealed evidence. | Replace the CLI, scripts, or installed skills. |
| Permit narrowly scoped, auditable actions when an operator chooses them. | Expose arbitrary shell commands, executor argv, or file reads. |
| Reuse existing configuration, validation, lifecycle, state, and receipt code. | Add an HTTP listener, daemon, database, remote execution, or scheduler. |
| Preserve worktree isolation, immutable prompts, sealed evidence, and review. | Automate merge, branch deletion, stalled-run termination, or acceptance. |

## Architecture

```text
MCP client
  └─ stdio JSON-RPC
       └─ agent-workflow-mcp entry point
            ├─ schemas and policy guard
            ├─ config.Settings / load_settings
            └─ existing Python services
                 ├─ doctor, pack, evaluation, ledger
                 ├─ state, sessions, lifecycle
                 └─ worktrees
```

The adapter calls library functions directly. It must not invoke the CLI as a
subprocess, scrape CLI output, or duplicate lifecycle logic. The CLI remains
the human-oriented interface and compatibility scripts remain wrappers around
the same service layer.

## Delivery sequence

### Phase 0: harden the service boundary

Extract any remaining CLI-dispatch-only behavior into small functions with
typed inputs and JSON-serializable output. Add an adapter-independent policy
boundary and tests. This prevents MCP from becoming a second workflow
implementation.

Acceptance criteria:

- Every exposed operation has a library-level test.
- Operational failures map to stable structured errors.
- MCP-specific code does not alter CLI defaults, receipts, or run state.

### Phase 1: read-only stdio MVP

Ship an optional extra and separate entry point. Select and pin/bound the MCP
SDK only after a current dependency-evaluation spike; do not assume a framework
now.

```toml
[project.optional-dependencies]
mcp = ["<selected MCP SDK>"]

[project.scripts]
agent-workflow-mcp = "agent_workflow.mcp_server:main"
```

Use local stdio only: one client process, no socket binding, and exit at stdin
close. Expose these tools first:

| Tool | Existing authority | Result |
|---|---|---|
| `workflow_doctor` | `doctor.run_doctor` | Environment and config capability report. |
| `workflow_list_runs` | `state.list_statuses` + observation | Run summaries. |
| `workflow_get_run_status` | `sessions.observe` | Durable/observed state and bounded capture. |
| `workflow_list_worktrees` | `worktrees.list_worktrees` | Repository worktree inventory. |
| `workflow_validate_pack` | `manifests.validate_pack` | Structure/checksum report. |
| `workflow_validate_evaluation` | `evaluation.validate_evaluation` | Plan identity/validation result. |
| `workflow_ledger` | `ledger.build_ledger` | Pack-to-run ledger data. |
| `workflow_evaluation_report` | report builder | Deterministic sealed-run report. |
| `workflow_verify_receipt` | `receipts.verify_seal` | Seal verification result. |

Resources may expose only metadata-safe artifacts: status, final receipt,
lifecycle receipts, and score set. Do not broadly publish raw prompt text,
executor output, patches, environment-derived paths, or evaluator-only oracle
material. Any later artifact retrieval must be explicit, bounded, and
authorized for a specific run.

### Phase 2: guarded mutations

Only after successful Phase 1 usage, add `workflow_create_worktree`,
`workflow_launch`, `workflow_restart`, and typed review/reject/accept tools.

| Tool | Required guardrails |
|---|---|
| Create worktree | Repository/destination inside configured roots; no inferred free-form branch. |
| Launch | Prompt/worktree/pack inside roots; configured executor name only; no explicit argv. |
| Restart | Existing durable session; preserve retry semantics. |
| Review lifecycle | Explicit actor, reason, disposition, and acceptance revision. |

Every mutation result returns session ID, authoritative run path, relevant
receipt/hash, and the exact state transition. Tool descriptions must state that
the action writes state or starts a process for client approval handling.

Do not initially expose worktree removal, attach/tail, interrupt, terminate,
kill, Inspect/SWE-bench, or pack-writing operations. Later high-impact tools
need a dedicated capability/config opt-in and explicit `confirm: true`; never
provide a generic `run_command` tool.

### Phase 3: evidence-aware client workflows

Consider only on proven operator friction:

- bounded retrieval of named sealed artifacts;
- paginated event and receipt inspection;
- an MCP prompt explaining prepare → launch → observe → review;
- client polling/subscriptions that do not mutate durable state.

Remote transport, cross-user sharing, and automatic recovery remain out of
scope.

## Policy and configuration

Add a separate `[mcp]` section rather than silently accepting all CLI paths:

```toml
[mcp]
enabled = true
read_roots = ["/lump/apps"]
write_roots = ["/lump/worktrees", "/lump/share/prompt-packs"]
max_log_lines = 200
allow_mutations = false
```

Rules:

1. Resolve paths before authorization; reject traversal, missing roots, and
   symlink escapes.
2. Repository, worktree, prompt, pack, output, and artifact paths must match a
   resolved configured root.
3. Accept configured executor names only—never executable paths or flags.
4. Cap and paginate log/event retrieval; never stream `tail` over MCP.
5. Default mutations to disabled and require both server policy and client
   approval to permit them.
6. Never return credentials, environment dumps, or evaluator-only oracle data.
7. Return stable error codes such as `outside_allowed_root`,
   `mutation_disabled`, `unknown_session`, and `invalid_transition`.

## Packaging and compatibility

- Keep MCP dependencies out of the core wheel and install them via an `mcp`
  extra.
- Use `src/agent_workflow/mcp_server.py` plus a small independently tested
  `mcp_policy.py` module.
- Keep dependency constraints compatible with the existing optional extras.
- Make `agent-workflow-mcp --help` work without starting a server.
- Document one local client configuration and that it inherits the invoking
  user's permissions.

## Test and release gates

| Layer | Required coverage |
|---|---|
| Unit | Schemas, containment, symlink escape, mutation flag, executor allowlist, error mapping. |
| Contract | Tool names, descriptions, schemas, and JSON-serializable output. |
| Integration | stdio handshake; temporary state root; no network listener. |
| Mutation | Temporary Git/worktree and fake executor; evidence/state match CLI semantics. |
| Security | Reject argv, out-of-root paths, oracle access, oversized capture, and unconfirmed destructive actions. |
| Regression | Existing unit suite, pack validation, release audit, wheel install, and CLI behavior. |

Do not promote beyond experimental until Phase 1 works with two local MCP
clients without client-specific adapter code; tools are sufficient to diagnose a
run without terminal parsing; mutation tools preserve evidence/lifecycle
invariants; and adversarial policy tests pass. Record observed operator friction
before expanding to Phases 2 or 3.

## Open decisions

1. Which current MCP SDK has the smallest stable stdio surface at implementation
   time?
2. Should sealed artifacts be resources, bounded tools, or both?
3. Which roots are safe defaults for a fresh install?
4. Does the target client reliably surface approval text, or must destructive
   confirmation remain entirely server-side?
5. What multi-client use case justifies mutations beyond the existing CLI and
   repo-local skills?

Until these are answered with real usage, Phase 1 is the maximum recommended
scope.
