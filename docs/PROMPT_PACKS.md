# Prompt packs

A prompt pack is a portable, reviewable execution plan for bounded delegated work. It contains phase manifests, ticket prompts, execution rules, evidence templates, and deterministic checksums.

## Canonical structure

```text
pack/
├── README.md
├── EXECUTION_PROTOCOL.md
├── DELEGATION_RUNBOOK.md
├── pack.yaml
├── MANIFEST.sha256
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

Repository-owned packs additionally pass `python3 scripts/audit-release-assets.py`, which validates backlog ownership, task-ID uniqueness, active-pack documentation, skill integration, links, mirrors, and checksums.

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
| [`deterministic-enforcement-foundations`](../prompt-packs/deterministic-enforcement-foundations/) | HARD-001, HARD-002, HARD-004, HARD-005 | Executable now. |
| [`execution-isolation-and-secrets`](../prompt-packs/execution-isolation-and-secrets/) | HARD-008, HARD-003, HARD-006 | Blocked until the foundation gate. |
| [`public-beta-trust-and-release`](../prompt-packs/public-beta-trust-and-release/) | HARD-007, HARD-009, HARD-010, REL-003, REL-004 | Blocked until both technical hardening gates. |
| [`mcp-server-next`](../prompt-packs/mcp-server-next/) | MCP-003 | Blocked until HARD-004, HARD-005, and HARD-007. |

The dependency/collision rationale is in [Determinism and security hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md). The source findings are in [Feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md).

## Execution authority

The pack describes work; it does not override runtime policy. Agent class, executor, model, authenticated principal, permissions, no-go authorization, worktree safety, sandbox policy, lifecycle controls, and backlog state remain enforced by application services and human decisions.

`EXECUTION_PROTOCOL.md` and `DELEGATION_RUNBOOK.md` are canonical portable files mirrored into scaffold assets. Update their canonical root copies first and run the release audit to detect drift.

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
