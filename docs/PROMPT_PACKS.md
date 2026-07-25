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

## Task manifests

Every task declares a stable ticket ID, tier, session ID, and prompt path. Dependencies may cross phases but must form one valid DAG. Unknown, duplicate, self, and cyclic dependencies are rejected.

A ticket may declare a structured result contract:

```yaml
result_contract:
  schema: contracts/task-result.schema.json
  required: true
```

The agent writes `result.json` to its handoff directory. The runner validates it against the pack-owned JSON Schema, records a collection receipt, and seals the validated copy with the run. Workflow bindings may read only bounded JSON Pointer values from sealed predecessor results.

## Prompt requirements

A ticket prompt should state:

- the writable scope;
- the required behavior and non-targets;
- acceptance commands or observable outcomes;
- expected evidence and completion handoff;
- stop conditions and unresolved prerequisites.

Do not embed host-specific absolute paths, credentials, private project names, mutable external documents, or assumptions that are not represented in the manifest or backlog.

## Execution authority

The pack describes work; it does not override runtime policy. Agent class, executor, model, permissions, no-go authorization, worktree safety, and lifecycle controls remain enforced by `agent-workflow` configuration and services.

`EXECUTION_PROTOCOL.md` and `DELEGATION_RUNBOOK.md` are canonical portable files mirrored into scaffold assets. Update their canonical root copies first and run the release audit to detect drift.

## Migration and maintenance

For an existing set of prompts:

1. scaffold a new pack;
2. assign stable ticket and session IDs;
3. move each prompt into one phase ticket;
4. express dependencies in manifests rather than prose order;
5. move shared background into bounded references;
6. add structured result contracts only where downstream automation needs them;
7. validate, review warnings, and archive deterministically.

Completed one-off prompt packs should not remain in the public source tree as permanent documentation. Git history and the changelog preserve implementation history. Retain only packs that are active development inputs; the current active pack is `prompt-packs/mcp-server-next/`.
