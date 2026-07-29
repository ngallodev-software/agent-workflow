# Prompt packs

A prompt pack is a portable, reviewable execution plan for bounded delegated work. It contains phase manifests, ticket prompts, execution rules, evidence templates, and deterministic checksums.

Pack roots are validated component-by-component without following links. Only
regular files and directories are accepted; symlinks, hard-linked files, FIFOs,
sockets, devices, and type changes are rejected and reported by relative entry
name. Archive staging consumes the exact validated inventory and adds a typed,
canonical `MANIFEST.json` with normalized paths, sizes, mode policy, and file
digests.

## Canonical structure

```text
pack/
├── README.md
├── EXECUTION_PROTOCOL.md
├── DELEGATION_RUNBOOK.md
├── pack.yaml
├── phase-0/
│   ├── README.md
│   ├── MASTER_IMPLEMENTATION_PROMPT.md
│   ├── task-manifest.yaml
│   └── tickets/
├── references/
├── scripts/
└── templates/
```

Create and validate a pack through the public CLI:

```bash
agent-workflow pack scaffold ./pack --phases 3
agent-workflow pack validate ./pack
agent-workflow pack archive ./pack ./pack.tar.zst
```

Repository-owned packs additionally pass `python3 scripts/audit-release-assets.py`, which validates backlog ownership, task-ID uniqueness, active-pack documentation, skill integration, links, and mirrors. A `MANIFEST.sha256` is an optional ignored transfer artifact; it is not required while a pack is being edited.

## Task manifests and ownership

Every task declares a stable ticket ID, tier, session ID, and prompt path. Dependencies may cross phases but must form one valid DAG. Unknown, duplicate, self, and cyclic dependencies are rejected.

A repository-owned implementation ticket also declares one canonical backlog owner:

```yaml
- id: "HARD-001"
  backlog_id: "HARD-001"
  tier: A
  session: "hardening-process-substrate"
  prompt: "tickets/HARD-001-bounded-process-substrate.md"
```

Review-only tasks declare `task_type: gate` and do not claim `backlog_id`. One backlog item may have several sub-tickets only inside one active pack; two active packs may never own the same item.

A ticket may declare a structured result contract:

```yaml
result_contract:
  schema: contracts/task-result.schema.json
  required: true
```

The agent writes `result.json` to its handoff directory. The runner validates it against the pack-owned JSON Schema, records a collection receipt, and seals the validated copy with the run. Workflow bindings may read only bounded JSON Pointer values from sealed predecessor results.

## Parallel execution

Missing dependency edges permit concurrent delegation, not shared writes. Every parallel ticket uses its own worktree and session. Integration is a separate reviewed step, and the phase gate reruns shared installed-product journeys after merge.

Prompt prose cannot override manifest dependencies. A blocked pack remains a planning artifact and must name its exact external prerequisites; presence in the repository does not make its backlog item ready.

## Prompt requirements

A ticket prompt states:

- canonical `backlog_id`, priority, dependencies, and parallel lane;
- writable scope and explicit non-targets;
- required behavior and deterministic authority boundary;
- installed-product acceptance journeys or strict future outcome;
- compact invariant matrices that cannot be covered efficiently end to end;
- security acceptance and adversarial cases;
- expected evidence and completion handoff;
- stop conditions and unresolved prerequisites.

Do not embed host-specific absolute paths, credentials, private project names, mutable external documents, or assumptions not represented in the manifest/backlog.

## Active packs

| Pack | Backlog ownership | State |
|---|---|---|
| [`deterministic-enforcement-foundations`](../prompt-packs/deterministic-enforcement-foundations/) | HARD-001, HARD-002, HARD-004, HARD-005 | Foundation implementations and `FOUND-GATE-01` accepted for the current tree. |
| [`execution-isolation-and-secrets`](../prompt-packs/execution-isolation-and-secrets/) | HARD-008, HARD-003, HARD-006 | HARD-008 accepted; HARD-003 and HARD-006 remain dependency-gated. |
| [`public-beta-trust-and-release`](../prompt-packs/public-beta-trust-and-release/) | HARD-007, HARD-009, HARD-010, REL-003, REL-004 | Blocked until both technical hardening gates. |
| [`mcp-server-next`](../prompt-packs/mcp-server-next/) | MCP-003 | Blocked until HARD-004, HARD-005, and HARD-007; future mutations must preserve the current parser-derived capability/catalog resources and launch-contract v2 command-context parity. |
| [`orchestrator-two-way-messaging`](../prompt-packs/orchestrator-two-way-messaging/) | BKL-001, BKL-002, MSG-001 through MSG-007 | Planning complete; DEC-001 decided; MSG-001 is ready, and later phases remain dependency-gated. |
| [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/) | PROC-001 through PROC-005 | Planning complete; phase 0 has four independent implementation lanes, followed by operator enforcement and an independent gate. |
| [`tmux-pane-identity-reliability`](../prompt-packs/tmux-pane-identity-reliability/) | PROC-006 | Ready; replaces mutable shared-window pane locations with durable pane identity and explicit run binding. |
| [`chatgpt-sealed-run-assessment`](../prompt-packs/chatgpt-sealed-run-assessment/) | CHATGPT-EVAL-001, CHATGPT-TDD-001 | Assessment and future-TDD artifacts completed; planned runtime work remains blocked behind its own implementation and gates. |

The dependency/collision rationale is in [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md). The local two-way messaging architecture and its collision-free implementation sequence are in [Durable two-way messaging](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md). The source findings are in [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md).

## Execution authority

The pack describes work; it does not override runtime policy. Agent class, executor, model, authenticated principal, permissions, no-go authorization, worktree safety, sandbox policy, lifecycle controls, and backlog state remain enforced by application services and human decisions.

`docs/references/EXECUTION_PROTOCOL.md` and `docs/references/DELEGATION_RUNBOOK.md` are the canonical portable files mirrored into scaffold assets. Update those conditional steering references first and run the release audit to detect drift.

Use `agent-workflow pack checksum` only when preparing a pack for transfer or unarchiving verification.

## Planned specification compiler

Prompt packs remain the execution bundle, but the proposed `agent-workflow-spec` sibling plugin will treat them as deterministic compiled artifacts of an approved machine-readable implementation specification. Existing hand-authored packs and the current validation/archive format remain supported. Generated packs will pair nuanced Markdown ticket prompts with machine task contracts, acceptance links, result schemas, and requirement traceability rather than replacing all prompts with JSON. See [Collaborative specification compiler and plugin-first decomposition](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md).

## Migration and maintenance

For an existing set of prompts:

1. confirm the canonical backlog item and that no active pack already owns it;
2. scaffold a new pack;
3. assign stable ticket/session IDs and `backlog_id` ownership;
4. express dependencies in manifests rather than prose order;
5. separate parallel tickets by writable surface and worktree;
6. move shared background into bounded references;
7. add structured result contracts only where downstream automation needs them;
8. validate, run the drift audit, review warnings, and archive deterministically.

Completed one-off prompt packs do not remain in the public source tree as permanent documentation. Git history and the changelog preserve implementation history.
