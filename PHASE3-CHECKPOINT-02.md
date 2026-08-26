# Phase 3 Checkpoint 02 — Cumulative skill-interface overlay

This checkpoint is cumulative from the authoritative Phase 2 source and includes all
Checkpoint 01 changes plus the second Phase 3 implementation slice.

## Included from Checkpoint 01

- hardened the primary `agent-workflow` skill as lifecycle authority;
- made use/do-not-use and headless/external decisions explicit;
- clarified durable identity, provenance, messaging, completion/review/acceptance,
  restart/recovery, prompt-pack, and benchmark boundaries;
- thinned specialized implementation/review/prompt-pack skills;
- made `agent-workflow delegate` the normal prompt-pack execution path.

## Checkpoint 02 additions

- added parser-backed extraction/validation for executable `agent-workflow` examples in
  shell-fenced skill blocks;
- validation uses the live core CLI parser with plugins disabled, preserving the parser as
  the only command authority and keeping plugin commands out of normal skill vocabulary;
- integrated skill-example validation into `scripts/audit-release-assets.py`, which is
  already part of release validation;
- documented the release-audit behavior in `scripts/README.md`;
- did not add narrow pytest cases or a parallel skill command schema.

## Testing policy

No test suite or release-validation command was run for this intermediate checkpoint.
Final Phase 3 verification remains a separate pass after implementation is complete.
