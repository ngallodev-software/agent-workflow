# Prompt Packs

Prompt packs package reproducible task instructions, result contracts, evaluation definitions, and handoff material. Historical implementation packs from the pre-0.8 architecture were removed during the breaking rewrite rather than carried forward as stale operational instructions.

## Authority

There is one scaffold source:

- packaged assets under `src/agent_workflow/assets/prompt-pack-root/` and `src/agent_workflow/assets/phase/`;
- `agent-workflow pack scaffold` materializes those assets into a self-contained source pack;
- `agent-workflow pack validate` validates the current format;
- `agent-workflow pack archive` creates deterministic archive-integrity evidence;
- `examples/three-phase-pack/` is a maintained example, not a second template authority.

The repository intentionally does **not** keep byte-identical prompt-pack mirrors under root `templates/` or compatibility helper copies under root `scripts/`. Generated packs still contain their portable helper scripts and report/source-baseline templates because those are part of the packaged scaffold.

Prompt packs must describe Agent Runs and workers without assuming an interactive host. A host-specific integration may be documented separately from the pack's durable workflow contract.

## Current format

Prompt packs have one workflow format: `agent-workflow/prompt-pack/v1`. The root `pack.yaml` is the only authoritative task/phase manifest and contains the phase graph, task IDs, Agent Run IDs, dependencies, prompt paths, optional backlog ownership, and result-contract references. Phase directories are human-readable material only and do not contain `task-manifest.yaml`.

`MANIFEST.json` is reserved for the deterministic archive-integrity inventory created by `agent-workflow pack archive`; it is not valid in an unpackaged source prompt pack. `MANIFEST.sha256` remains the optional source-pack checksum sidecar.

Create a new pack with:

```bash
agent-workflow pack scaffold /path/to/new-pack --phases 3 --name example-pack
agent-workflow pack validate /path/to/new-pack
```
