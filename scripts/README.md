# Compatibility scripts

These filenames preserve the helper interface used by earlier prompt packs. They are intentionally thin wrappers around the installed `agent-workflow` CLI. Do not add independent lifecycle logic here; durable behavior belongs in `src/agent_workflow/`.

## Release evidence

`release-check.sh` remains the consolidated technical validation entrypoint. It now records pytest JUnit XML and invokes `release-evidence.py` on both success and failure. The evidence generator validates `release/release-policy.json` and `release/dependency-lock.json`, writes CycloneDX SBOM and build-provenance files, and summarizes technical and governance status in `release-evidence.json`.

Use `AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1` only for a release authorization gate; development validation records open blockers without converting them into a failed technical check. See [`docs/RELEASE_EVIDENCE.md`](../docs/RELEASE_EVIDENCE.md).
