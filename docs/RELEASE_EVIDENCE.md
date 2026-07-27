# Release evidence and blocker automation

REL-005 provides one machine-readable release-evidence path without converting open governance or compatibility work into a false release claim.

## Authoritative inputs

- [`release/release-policy.json`](../release/release-policy.json) records license, vulnerability-channel, and compatibility-matrix status.
- [`release/dependency-lock.json`](../release/dependency-lock.json) pins every direct dependency declared by `pyproject.toml` and records its dependency groups and original requirement strings.
- JSON Schemas under [`schemas/`](../schemas/) define the policy, lock, release summary, and build-provenance contracts.

The compatibility entries are candidates until REL-003 accepts clean-host evidence. A `candidate` matrix is a declared test target, not a support statement.

The committed dependency lock is intentionally direct-only. Complete transitive resolution with hashes, independent reproducibility, and authenticated signing/attestation remain HARD-010.

## Generate evidence

The normal technical gate writes durable evidence even when a test or collection step fails:

```bash
AGENT_WORKFLOW_RELEASE_EVIDENCE_DIR=build/release-evidence \
  ./scripts/release-check.sh
```

The output directory contains:

- `pytest-junit.xml` — structured pytest results;
- `sbom.cdx.json` — CycloneDX 1.5 SBOM from the synchronized direct lock;
- `build-provenance.json` — source-tree digest, Git state when available, builder metadata, input digests, and supplied artifact digests;
- `release-evidence.json` — blocker and technical-check summary with digests for every evidence file.

Pass built artifacts into provenance with a colon-separated list:

```bash
AGENT_WORKFLOW_RELEASE_ARTIFACTS='dist/agent_workflow.whl:dist/agent_workflow.tar.gz' \
  ./scripts/release-check.sh
```

By default, open governance blockers are recorded but do not convert a successful development validation into a failing command. The public-release gate must enforce them:

```bash
AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1 ./scripts/release-check.sh
```

The enforced command exits `3` when technical checks pass but release blockers remain. Technical failures preserve their original nonzero exit and are recorded as `technical_failure`.

Evidence can also be regenerated without running the full suite:

```bash
python3 scripts/release-evidence.py \
  --output-dir build/release-evidence \
  --test-results build/release-evidence/pytest-junit.xml
```

## Status semantics

- `ready`: technical checks pass, structured tests pass, and the license, security channel, and accepted compatibility evidence are configured.
- `blocked`: technical evidence is valid, but at least one governance/compatibility decision is open or structured tests were not supplied.
- `technical_failure`: a test, lock, metadata-consistency, or technical release check failed.

The evidence summary is diagnostic authority for release readiness; it is not a signature, an external compatibility result, or an independent release authorization.

