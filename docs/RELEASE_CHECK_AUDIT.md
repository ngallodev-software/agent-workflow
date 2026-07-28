---
name: release-check-audit
description: Audit of release-check.sh coverage against P0 blockers and evidence quality
---

# Release Check Audit

## REL-005 implementation update — 2026-07-27

REL-005 is complete. `release-check.sh` now writes pytest JUnit XML and invokes the schema-validated release-evidence generator on both success and failure. The generator validates explicit license/security/compatibility policy state, verifies a synchronized direct-dependency lock, emits a CycloneDX 1.5 SBOM and source/build provenance, records optional artifact digests, and can enforce blockers with `AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS=1`. See [Release evidence](RELEASE_EVIDENCE.md).

The detailed gap analysis below is the pre-REL-005 audit baseline. Its open license, monitored-channel, and compatibility findings remain accurate as REL-001, REL-002, and REL-003 blockers; its statements that REL-005 evidence automation is missing are superseded by this update. Full transitive hashes, reproducible builds, and authenticated signing remain HARD-010.

## Current Checks Coverage

### 1. Python Bytecode Cleanup
- **Check:** `cleanup_bytecode()` trap and `find src tests scripts -type d -name __pycache__ -prune -exec rm -rf {} +`
- **Validates:** Build environment hygiene; ensures no stale compiled artifacts affect build
- **Evidence:** Implicit (trap runs before exit)
- **BACKLOG mapping:** None directly, but supports clean reproducible builds

### 2. Release Asset Audit
- **Check:** `python3 scripts/audit-release-assets.py`
- **Validates:**
  - All repository files are present and correctly enumerated
  - Text integrity (no NUL bytes, no CRLF line endings)
  - UTF-8 encoding validity
  - No unresolved template placeholders in non-asset code
  - Skill directory structure, naming, and metadata
  - JSON and JSON Schema syntax validity
  - TOML file syntax (including examples in README)
  - YAML file syntax
  - Version consistency across all documented locations (VERSION, pyproject.toml, __init__.py, CLI help, docs)
  - Portable script mirrors are present and match canonical versions
  - Documentation mirror groups stay synchronized
  - Shell entrypoint executability
  - Markdown link resolution (no broken local links)
  - ignored/generated checksum files are excluded from repository cleanliness checks
- **Evidence:** audit script prints "release assets: valid"; transfer archives carry their own canonical manifest and optional sidecar checksum
- **BACKLOG mapping:** None directly, but foundational for reproducible distribution

### 3. Python Compile Check
- **Check:** `python3 -m compileall -q src tests scripts`
- **Validates:** All Python source code is syntactically valid and compiles
- **Evidence:** Exit code 0 (no output with `-q` flag)
- **BACKLOG mapping:** None directly; supports build quality

### 4. Shell Syntax Validation
- **Check:** `bash -n install.sh uninstall.sh bin/agent-workflow` + `find templates src/agent_workflow/assets -type f -name '*.sh' -print0` piped to `bash -n` per file
- **Validates:** All shell scripts are syntactically correct and executable (covered by audit-release-assets.py for executability)
- **Evidence:** Exit code 0 for each file
- **BACKLOG mapping:** None directly; supports installer and CLI stability

### 5. Python Test Suite
- **Check:** `python3 -m pytest -q`
- **Validates:**
  - **Acceptance journeys** (`tests/acceptance/`): installed wheel CLI discovery, pack validation, Git worktree operations, executor launch/restart, durable steer/watch/ack replay, provider-event collection, workflow validation/scheduling/resume, template expansion, evaluation comparisons
  - **Invariant matrices** (`tests/invariants/`): durable state append-only ordering, security boundary enforcement, seal integrity, scheduler dependency rules, provider accounting, evaluation identity
  - **Release checks** (`tests/release/`): asset audit, schema validity, shell syntax, documented-command matching
  - **Future specifications** (`tests/future/`): approved backlog behavior marked as `xfail(strict=True)` (currently: `BKL-002` late steering journey)
- **Evidence:** pytest output; exit code 0 means all tests passed
- **BACKLOG mapping:**
  - **BKL-001** (durable message cursors): covered by `tests/acceptance/test_consumer_cursor_journey.py` and `tests/invariants/test_consumer_cursors.py` (installed-wheel replay, crash windows, reconstruction, independent consumers, and digest/path integrity)
  - **BKL-002** (post-launch steering): covered by `tests/future/test_late_steering_journey.py` (future specification, currently xfail)
  - **REL-003** (compatibility matrix): NOT covered by release-check.sh (opt-in live tests only)

### 6. Pack Validation
- **Check:** `python3 -m agent_workflow pack validate examples/three-phase-pack`
- **Validates:** Example prompt pack structure, manifest, schemas, and ready-to-run state
- **Evidence:** Exit code 0 (CLI output shows success)
- **BACKLOG mapping:** None directly; supports example pack reproducibility

### 7. JSON Schema Syntax
- **Check:** Inline Python loop loads each file from `schemas/` directory as JSON
- **Validates:** All JSON Schema files have valid JSON syntax
- **Evidence:** Script prints "JSON schemas: valid syntax"
- **BACKLOG mapping:** None directly; supports schema distribution

---

## Jenkins Verification

The local `agent-workflow-local` Jenkins job was verified independently of the default shell gate:

- Build #23 checked out `origin/master` at `5de662c`.
- The pipeline created its isolated Python environment and installed `pytest`, `jsonschema`, `build`, and `setuptools`.
- The installed-product suite completed with `94 passed, 2 skipped, 5 xfailed`.
- Release checks passed, `agent_workflow-0.2.5-py3-none-any.whl` was built, and the global wheel install stage completed with `mcp==1.28.1`.
- The job is restricted to `refs/heads/master`; it has no SCM trigger (`<triggers/>`), so commit-trigger behavior remains REL-006 and has not been verified.

This closes the local pipeline execution failure, not the public release gates. Jenkins success does not prove clean-host compatibility, provider compatibility, or release provenance.

## Gap Analysis

### P0 Blockers from BACKLOG.md

| ID | Priority | State | Blocker | Coverage | Gap |
|---|---|---|---|---|---|
| **BKL-001** | P0 | ready | Durable per-consumer message cursors, restart recovery, duplicate safety, cursor advancement | Implemented in `src/agent_workflow/consumer_cursors.py`; focused acceptance and invariant evidence cover the cursor contract | **Promote the strict acceptance evidence through the phase gate** |
| **BKL-002** | P0 | ready | Post-launch steering for detached runs (delivered/applied/rejected evidence) | Covered only by a strict future specification (xfail) | **No runtime delivery/application evidence yet** |
| **REL-001** | P0 | needs-decision | Select and add license, matching package metadata | **NOT CHECKED** | **No check for LICENSE file presence, license classifier in pyproject.toml, or license header matching** |
| **REL-002** | P0 | blocked | Establish vulnerability-reporting channel and update SECURITY.md | **NOT CHECKED** | **No check that SECURITY.md contains a monitored contact or private mechanism** (currently reads "pre-public-release" and says this is a blocker) |
| **REL-003** | P0 | ready | Define supported Linux/Python/tmux/executor matrix; run live compatibility journeys | **NOT CHECKED BY release-check.sh** | **Live compatibility tests are opt-in only** (separate `pytest -m live` with environment flags; not run by default gate) |
| **REL-004** | P0 | needs-decision | Release ownership, signing, support, and security-update policy | **NOT CHECKED** | **No governance or signed-provenance gate exists** |
| **SEC-001** | P0 | ready | Bounded subprocess execution | **NOT CHECKED** | **Current release checks do not enforce timeout, output, process-group, or environment limits** |
| **SEC-002** | P0 | ready | Preventative execution scope and prompt-pack file integrity | **NOT CHECKED** | **Scope checks are post-run and manifest/archive handling needs an explicit symlink/special-file policy** |
| **SEC-003** | P0 | ready | MCP privacy/path/receipt hardening | **NOT CHECKED** | **Read-only MCP behavior is not a public-release security gate** |
| **SEC-004** | P0 | ready | Immutable launch authority | **NOT CHECKED** | **Runner/evaluation paths still have projection-to-authority coupling** |

### P1 release-evidence gaps

| ID | Gap | Required exit evidence |
|---|---|---|
| **REL-005** | Completed | Policy/blocker checks, JUnit results, synchronized direct lock, CycloneDX SBOM, source/build provenance, and optional artifact digests are implemented |
| **REL-006** | Jenkins SCM trigger | A local repository commit causes a build of the matching master revision; the current successful build was manually triggered |
| **REL-007** | Clean-machine install/uninstall and provider cohort | Scrubbed install/uninstall records and sealed controlled provider/workflow evidence |

### Recommended Gap Fixes (Priority Order)

#### 1. **License Presence and Metadata Check** (Critical blocker)
- **What to add:** Check that `LICENSE` file exists at repository root
- **Why:** `REL-001` requires a selected license; distribution cannot happen without it
- **How to implement:**
  ```python
  if not (ROOT / "LICENSE").is_file():
      fail("LICENSE: file not found (REL-001 blocker)")
  ```
- **Evidence produced:** Pass/fail from audit script
- **Suggested integration:** Add to `scripts/audit-release-assets.py` in the audit loop

#### 2. **License Classifier Check** (Critical blocker)
- **What to add:** Verify pyproject.toml has a license classifier matching the LICENSE file
- **Why:** Package metadata must declare the license for distribution platforms
- **How to implement:**
  ```python
  # Check that at least one license classifier exists
  classifiers = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8")).get("project", {}).get("classifiers", [])
  if not any(c.startswith("License ::") for c in classifiers):
      fail("pyproject.toml: missing license classifier (REL-001 blocker)")
  ```
- **Evidence produced:** Pass/fail from audit script
- **Suggested integration:** Add to `scripts/audit-release-assets.py`

#### 3. **Vulnerability Reporting Channel Check** (Critical blocker)
- **What to add:** Check that SECURITY.md contains a non-placeholder monitored contact mechanism
- **Why:** `REL-002` requires a real channel; placeholder text indicates blocker is not resolved
- **How to implement:**
  ```python
  security_text = (ROOT / "docs" / "SECURITY.md").read_text(encoding="utf-8")
  if "pre-public-release" in security_text or "does not yet have a monitored" in security_text:
      fail("docs/SECURITY.md: vulnerability-reporting channel not yet established (REL-002 blocker)")
  if not any(pattern in security_text for pattern in ["security@", "vulnerabilities@", "security.md", "OpenSSF"]):
      fail("docs/SECURITY.md: no monitored contact mechanism found (REL-002 blocker)")
  ```
- **Evidence produced:** Pass/fail from audit script
- **Suggested integration:** Add to `scripts/audit-release-assets.py`

#### 4. **Supported Compatibility Matrix Definition** (Critical blocker)
- **What to add:** Check that docs/TESTING.md or docs/PUBLIC_RELEASE_READINESS.md declares the first supported host/executor matrix
- **Why:** `REL-003` requires explicit declaration of supported versions before public release
- **How to implement:**
  ```python
  # Check for explicit matrix definition in TESTING.md or PUBLIC_RELEASE_READINESS.md
  testing_doc = (ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
  release_doc = (ROOT / "docs" / "PUBLIC_RELEASE_READINESS.md").read_text(encoding="utf-8")
  combined = testing_doc + release_doc
  
  matrix_keywords = ["Linux", "Python 3.11", "Python 3.12", "tmux", "Claude", "Codex"]
  if not all(k in combined for k in matrix_keywords):
      fail("docs: supported host/executor matrix not fully defined (REL-003 blocker)")
  ```
- **Evidence produced:** Pass/fail from audit script
- **Suggested integration:** Add to `scripts/audit-release-assets.py` or new dedicated script

#### 5. **Live Compatibility Evidence Requirement** (Important validation)
- **What to add:** Document that release-check.sh should recommend running live tests before declaring release readiness
- **Why:** `REL-003` requires "run live compatibility journeys on representative clean hosts" but these are opt-in
- **How to implement:**
  - Add note to release-check.sh output or new gate step listing required live test runs
  - Document in PUBLIC_RELEASE_READINESS.md that `pytest -m live` is part of release gate (not just default suite)
- **Evidence produced:** Test output from live tests
- **Suggested integration:** Add requirement to docs and/or release-check.sh post-checks

---

## Evidence Quality Assessment

### Objective vs. Subjective Checks

| Check | Type | Reproducibility | Reviewer Proof |
|---|---|---|---|---|
| Release asset audit | **Objective** | Fully reproducible; deterministic source inventory and syntax/link checks | Audit exit code; transfer archive manifest/checksum when an archive is produced |
| Python compile | **Objective** | Fully reproducible; deterministic syntax check | compileall exit code; file-by-file validation |
| Shell syntax | **Objective** | Fully reproducible; deterministic AST check | bash -n exit code per file |
| Test suite | **Mostly objective** | Reproducible if executor/model output is seeded; pytest journals events | Test output, sealed evidence from executor runs, acceptance journey state |
| Pack validation | **Objective** | Reproducible if pack structure is static | pack validate exit code; optional transfer checksum verification |
| JSON Schema syntax | **Objective** | Fully reproducible; deterministic validation | JSON schema validator exit code |
| License presence | **Objective** | Fully reproducible; file existence check | LICENSE file existence |
| Vulnerability channel | **Partly subjective** | Heuristic pattern matching (email, security contact); human review still needed | SECURITY.md text search + manual review of actual contact mechanism |
| Compatibility matrix | **Subjective** | Declaration is objective; actual testing is opt-in | Documented declared versions + live test evidence (separate) |

### Durability of Evidence

- **Permanent (suitable for release archive):**
  - Archive `MANIFEST.json` and optional archive sidecar SHA256
  - Test output from acceptance suite (pytest JSON report)
  - Sealed evidence from live executor runs (in XDG state directory)
  - License file copy
  
- **Ephemeral (not suitable for archive):**
  - compileall and bash -n validation (exist at build time only; no artifact remains)
  - pytest default output (terminal text, not structured)
  - SECURITY.md pattern match results (documentation review, not sealed)

### Recommendations for Evidence Archiving

1. **Capture pytest results as JSON** for durable evidence:
   ```bash
   pytest --json-report --json-report-file=release-test-results.json
   ```

2. **Seal the archive manifest and license** in release artifacts:
   - Generate a transfer checksum only when producing the archive
   - Include LICENSE in distribution package (setuptools does this automatically)

3. **Document live compatibility runs** as a separate gate:
   - Record host OS, Python version, tmux version, executor type
   - Capture test output with timestamps and sealed evidence references
   - Store in release branch or release notes

---

## Recommendations

### High Priority

1. **Add license checks to release-check.sh** (blocks REL-001; part of REL-005)
   - [x] Check configured license file exists when policy claims readiness
   - [x] Require matching SPDX/package metadata when policy claims readiness
   - [x] Integrate policy/lock schema and synchronization checks into `audit-release-assets.py`

2. **Add vulnerability-channel check to release-check.sh** (blocks REL-002; part of REL-005)
   - [x] Verify the configured non-placeholder contact is published in `SECURITY.md`
   - [x] Keep a blocked policy status until a real monitored channel is configured
   - [x] Integrate policy/lock schema and synchronization checks into `audit-release-assets.py`

3. **Add compatibility matrix check** (blocks REL-003; part of REL-005)
   - [x] Commit a machine-readable candidate matrix without describing it as supported
   - [x] Require clean-host evidence before matrix status can become `supported`
   - [x] Record candidate combinations and evidence references in release policy

### Medium Priority

4. **Make pytest results durable** (REL-005)
   - [x] Emit pytest JUnit XML using pytest built-in support
   - [x] Digest JUnit XML in `release-evidence.json` and build provenance

5. **Document release gate enforcement**
   - [x] Update public-release and release-evidence guidance
   - [x] Document default and enforced release-evidence commands

### Low Priority

6. **Improve evidence capture**
   - [ ] Consider capturing compileall and shell-syntax results as structured output (optional; exit code suffices)
   - [ ] Add timestamp and version metadata to test evidence

7. **Configure Jenkins commit triggering** (REL-006)
   - [ ] Add the local SCM polling/trigger policy to the job configuration
   - [ ] Commit a harmless documentation change and verify the resulting build checks out that revision
   - [ ] Keep the local-only boundary and clean temporary environments

---

## Summary

**Current release-check.sh coverage:**
- ⚠️ Exercises the canonical BKL-001 cursor implementation; phase-gate review and shared post-integration journeys remain separate
- ⚠️ Includes the BKL-002 strict future specification as an expected failure; it does not prove runtime late-steering delivery
- ✅ Validates distribution asset integrity, JSON/YAML/TOML syntax, link resolution
- ✅ Runs acceptance and invariant test suites
- ✅ Records explicit blocker checks for license selection (REL-001), vulnerability reporting (REL-002), and compatibility evidence (REL-003) without fabricating readiness
- ✅ Implements the structured evidence/provenance portion of REL-005; REL-004 and the remaining technical/security gates stay separate
- ⚠️ Live compatibility tests (REL-003) are opt-in, not part of default gate

**Evidence quality:**
- Objective, reproducible checks for most gates (assets, syntax, tests)
- Pytest results are archived as JUnit XML and digest-bound into the release summary and provenance
- Live compatibility evidence requires separate run with explicit environment flags

**Before marking "ready for release," ensure:**
1. LICENSE file selected and committed (REL-001)
2. Vulnerability-reporting channel established in SECURITY.md (REL-002)
3. Supported host/executor matrix explicitly declared (REL-003)
4. Live compatibility tests run on representative hosts and documented (REL-003)
5. Run the enforced release evidence gate and require `status: ready`
