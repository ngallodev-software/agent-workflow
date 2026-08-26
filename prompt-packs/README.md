# Active Prompt Packs

No implementation prompt pack is active in this source tree.

The pre-0.8 implementation packs and completed Phase 0–2 closeout handoff were intentionally removed so stale instructions cannot be executed accidentally. New work should be selected from `docs/BACKLOG.md`, designed against the current architecture, and packaged according to `docs/PROMPT_PACKS.md`.

Generated packs must use the current `Workflow -> Task -> Agent Run -> Worker` model and must not introduce a terminal-host dependency into core. New active packs use `agent-workflow/prompt-pack/v1` with the complete task graph in root `pack.yaml`; do not add per-phase task manifests or workflow metadata in `MANIFEST.json`.
