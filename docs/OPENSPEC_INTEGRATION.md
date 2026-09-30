# OpenSpec integration

Agent-Workflow treats OpenSpec as an upstream **specification/planning authority** and keeps
execution, evidence, evaluation, review, recovery, and acceptance as Agent-Workflow
responsibilities.

The first qualified import surface is intentionally narrow:

- OpenSpec `1.13.2` exactly;
- package-owned `spec-driven` schema version `1`;
- one local Git repository and one active change;
- a clean, committed planning revision;
- strict OpenSpec validation;
- no project/user schema override;
- no OpenSpec store or multi-repository import.

This is a versioned compatibility surface, not a claim that arbitrary future OpenSpec releases
have equivalent semantics.

## Boundary

```text
OpenSpec change
   |
   | documented CLI JSON + frozen planning artifacts
   v
agent-workflow/source-specification-import/v1
   |
   v
agent-workflow/native-job/v2
   |
   v
Agent Run
   execution / evidence / evaluation / review / acceptance
```

The imported pack is self-contained for Agent-Workflow preparation and execution. OpenSpec is not
consulted again after import.

Legacy `agent-workflow/native-job/v1` remains supported and continues to negotiate the immutable
SpecGen/Agent-Workflow shared contract bundle. The v1 schema is not reinterpreted as OpenSpec.
New OpenSpec imports use `native-job/v2`, which is owned by Agent-Workflow and has no
`bundle_provenance` field.

## Import

Prepare an Agent-Workflow-owned execution policy separately from the OpenSpec change:

```json
{
  "path_policy": {
    "allowed_paths": ["src"],
    "forbidden_paths": []
  },
  "acceptance_commands": [
    {
      "id": "test",
      "argv": ["python3", "-m", "pytest", "-q"],
      "cwd": ".",
      "timeout_seconds": 300,
      "result_format": "exit-code",
      "junit_path": null
    }
  ],
  "criteria": [
    {
      "id": "tests-pass",
      "description": "The declared test command passes.",
      "acceptance_command_ids": ["test"]
    }
  ],
  "review_requirement": {
    "required": false,
    "independent": false
  }
}
```

Then import:

```bash
agent-workflow pack import-openspec /path/to/repo CHANGE /path/to/generated-pack \
  --job-policy /path/to/job-policy.json
```

The destination must be outside the source repository so import cannot make the frozen source
revision dirty.

The importer records:

- OpenSpec executable identity and SHA-256;
- resolved package schema and template SHA-256 values;
- raw JSON reports from version/schema/template/status/validation/apply/show commands;
- exact source Git revision and branch;
- SHA-256 for the planning artifacts used by the import;
- stable Agent-Workflow task IDs mapped to OpenSpec task locators and source-line hashes.

Generated jobs automatically forbid `openspec/` from writable execution scope.

## Planning verification is not execution acceptance

OpenSpec task text is worker-visible planning input. It may describe how an author expects a task
to be checked, but Agent-Workflow does not parse that prose into executable acceptance authority.

In particular:

- a command mentioned in `tasks.md` does not become an acceptance command;
- OpenSpec agent verification workflows are not deterministic host validators;
- hidden/external oracle material remains Agent-Workflow-owned;
- independent review remains Agent-Workflow-owned;
- executable commands enter through the explicit Agent-Workflow job policy and are frozen with the
  native job.

This keeps the implementation worker from implicitly choosing the authoritative test for its own
work.

## Source binding

At v2 preparation, Agent-Workflow verifies that the selected worktree:

1. is at the exact imported Git revision;
2. is clean at first launch;
3. contains byte-identical frozen OpenSpec planning artifacts.

The absolute path recorded during import is provenance only. A fresh worktree may live elsewhere as
long as the revision and imported planning bytes match.

The source specification receipt is copied into run-local evidence and sealed with the run.

## Compatibility and retirement boundary

This integration does **not** archive SpecGen or rewrite historical artifacts.

Current compatibility policy:

- `native-job/v1`: frozen legacy SpecGen/shared-contract path;
- `native-job/v2`: OpenSpec source-specification path, no SpecGen negotiation;
- the shared contract package remains installed while supported v1 jobs exist;
- new planning work should prefer OpenSpec rather than creating new SpecGen authoring state;
- removal of the mandatory shared-contract dependency is a later compatibility change after v2
  migration evidence is complete.

SpecGen capabilities that were actually execution invariants—source binding, fail-closed lowering,
result contracts, writable scope, evaluation/oracle identity, and review requirements—remain
Agent-Workflow concerns rather than being discarded with the authoring system.

## Deferred

The initial integration deliberately does not support:

- custom/forked OpenSpec schemas;
- project or user schema overrides;
- OpenSpec stores;
- multi-repository worksets;
- arbitrary future OpenSpec versions;
- automatic translation of planning prose into validators;
- OpenSpec archive operations as Agent-Workflow lifecycle actions.

Each requires separate qualification rather than widening the v1 import receipt silently.
