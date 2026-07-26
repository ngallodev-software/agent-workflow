# Release Blockers Audit

**Date:** 2026-07-26
**Status:** Release candidate assessment  
**Scope:** P0 blockers from BACKLOG.md and PUBLIC_RELEASE_READINESS.md

---

## Executive Summary

The governance blockers remain open: license selection, durable-control objectives, vulnerability reporting, supported-host evidence, and release ownership/signing. The determinism/security assessment also identifies four P0 engineering controls required before a public preview. Jenkins build #16 proves the local CI pipeline can build, test, and install the current tree, but it does not close release governance or clean-host/provider evidence.

---

## P0 Blockers Summary Table

| ID | Blocker | Current State | Exit Evidence Requirement | Decision Dependencies | Estimated Effort |
|---|---|---|---|---|---|
| REL-001 | License selection and adoption | needs-decision | `LICENSE` file in repo root + matching `project.toml` metadata + verified distribution compliance | None (independent) | 2-4h (research + metadata update) |
| DEC-001 | Durable-control service objectives | needs-decision | Recorded decision: storage model, failure semantics, ordering scope, idempotency, max latency SLO | None (independent) | 4-8h (design workshop) |
| REL-002 | Vulnerability reporting channel | blocked | Real monitored email or private disclosure mechanism + updated `SECURITY.md` with contact details | None (independent, external coordination) | 4-8h (infrastructure + doc update) |
| REL-003 | Supported host/executor matrix | ready | Live compatibility test results on clean hosts for each declared Linux/Python/tmux/executor/model combination | None (independent, but requires execution) | 8-16h (per-platform testing) |
| REL-004 | Release ownership and signing policy | needs-decision | Named maintainer process, protected tags, signed artifact policy, support window, and security-update ownership | None | 4-8h (governance decision) |
| DEC-001 (blocking BKL-001) | Service objectives for durable messages | needs-decision | Decision on cursor durability, restart recovery guarantees, handling idempotency scope | Prerequisite for BKL-001 implementation | Included in DEC-001 |
| SEC-001 | Bounded subprocess substrate | ready | Timeout/output/process-group/resource controls and sanitized/redacted execution evidence across host-tool call sites | None | 16-24h |
| SEC-002 | Preventative execution and pack integrity controls | ready | Sandbox/write boundary plus symlink/special-file policy with acceptance evidence | None | 16-32h |
| SEC-003 | MCP read-boundary hardening | ready | Metadata-only message default, no-follow path validation, stable errors, and safe receipt reads | None | 8-16h |
| SEC-004 | Immutable launch authority | ready | Immutable launch contract consumed by runner/evaluator; mutable status is projection only | None | 8-16h |

---

## Decision Dependencies

### DEC-001: Durable-Control Service Objectives

**Blocks:** BKL-001 (durable message cursors), BKL-002 (post-launch steering), potentially BKL-007 (host routing)

**What must be decided:**
- Storage and failure model (process-scoped, machine-local, replicated, distributed)
- Ordering scope (per-consumer, per-workflow, global)
- Producer model (blocking, fire-and-forget, at-most-once, at-least-once)
- External-effect idempotency guarantees
- Maximum no-wakeup latency (SLO)

**Why blocking:** BKL-001 implementation assumes specific cursor semantics and recovery behavior; without DEC-001 resolution, the exit evidence will be ambiguous (what does "restart recovery" mean?).

**Cross-reference:** BACKLOG.md§DEC-001, OPERATIONS.md§durable-messages (when available)

---

### REL-001: License Selection

**Blocks:** Package publication, public repository hosting, contributor license terms

**What must be decided:**
- Open-source license choice (MIT, Apache 2.0, GPL, AGPL, other)
- License statement in repo root
- Package metadata classifier in `pyproject.toml` or `setup.cfg`
- Distribution policy (PyPI, conda-forge, source-only)

**Why blocking:** Public repositories and package indices require explicit license declarations; ambiguous licensing blocks adoption and legal review by users.

**Cross-reference:** PUBLIC_RELEASE_READINESS.md§Blocking decisions, BACKLOG.md§REL-001

---

### REL-002: Vulnerability Reporting Channel

**Blocks:** Security transparency, user trust, incident response

**What must be decided:**
- Monitored vulnerability reporting channel (email, private GitHub disclosure, security.txt, other)
- Named security contact or team
- Response SLA and escalation procedure

**Why blocking:** Public release without a real, monitored channel risks unresponded security reports and abandonment perception.

**Cross-reference:** PUBLIC_RELEASE_READINESS.md§Blocking decisions, SECURITY.md (needs creation)

---

### REL-003: Supported Host/Executor Matrix

**No decision dependency, but requires execution.**

**Matrix dimensions:**
- Linux kernel versions (e.g., 5.10+, 6.0+)
- Python versions (3.10, 3.11, 3.12+)
- tmux versions (3.0+, 3.2+, 3.3+)
- Executor types (Claude, Codex, local)
- Provider versions (Claude API versions, Codex versions)

**Why blocking:** Live compatibility evidence is the only proof that the product works outside development environments. CI passing is necessary but not sufficient.

**Cross-reference:** PUBLIC_RELEASE_READINESS.md§Release gate, TESTING.md§live-compatibility, BACKLOG.md§REL-003

---

## Exit Evidence Checklist

### Jenkins local pipeline verification

- [x] Jenkins job `agent-workflow-local` completed build #16 successfully on `origin/master` at `8b937a0`
- [x] Isolated Jenkins Python environment provisioned with `pytest`, `jsonschema`, `build`, and `setuptools`
- [x] Release checks passed: `35 passed, 2 skipped, 1 xfailed`
- [x] Wheel built: `agent_workflow-0.2.2-py3-none-any.whl`
- [x] Local editable install completed successfully
- [ ] Commit-trigger/polling behavior is configured and verified; current job configuration has no SCM trigger
- [ ] Jenkins output is archived as structured, scrubbed release evidence

This is internal CI evidence only. It does not substitute for REL-003 clean-host compatibility, REL-007 install/uninstall evidence, or a supported provider cohort.

### Determinism/security P0 controls

- [ ] SEC-001: bounded subprocess substrate is implemented and migrated across host-tool/evaluation call sites
- [ ] SEC-002: preventative writable-path enforcement and prompt-pack symlink/special-file policy are implemented
- [ ] SEC-003: MCP message privacy and component-safe path/receipt handling are implemented
- [ ] SEC-004: immutable launch contract is authoritative for runner and evaluation inputs

Detailed findings and source observations are recorded in [FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md).

### REL-001: License Selection

**Completion requires ALL of:**

- [ ] `LICENSE` file exists in repository root with full license text
- [ ] `pyproject.toml` includes `license = { text = "..." }` or similar (per build backend)
- [ ] Package classifier set (e.g., `"License :: OSI Approved :: Apache Software License"`)
- [ ] LICENSE.md or COPYING.md created if needed for distribution clarity
- [ ] Any existing code with different or no license header is clarified (relicense or exclude)
- [ ] Maintainer confirms license choice through commit message or ADR

**Test:** `python -m build` succeeds; `pip index versions agent-workflow` shows license classifier

---

### DEC-001: Durable-Control Service Objectives

**Completion requires:**

- [ ] Decision document (ADR or DECISION.md) filed with:
  - Storage model choice and rationale (e.g., "process-scoped JSONL, no remote replication")
  - Failure model (what happens when process crashes, host reboots, disk full)
  - Ordering guarantee (e.g., "per-workflow FIFO, no global total order")
  - Idempotency scope (e.g., "handling disposition determined by state ID + handler signature, re-handling with identical input is safe")
  - Maximum no-wakeup latency (e.g., "10ms under normal load, no strict guarantee under saturation")
- [ ] DEC-001 decision is recorded in BACKLOG.md and moved from `needs-decision` to `decided` state
- [ ] BKL-001 and BKL-002 exit evidence updated to reference the decision

**Test:** BACKLOG.md§DEC-001 state is no longer `needs-decision`; implementation of BKL-001 references decision ID

---

### REL-002: Vulnerability Reporting Channel

**Completion requires:**

- [ ] Monitored vulnerability reporting email alias or private disclosure form created (real infrastructure, not a placeholder)
- [ ] `SECURITY.md` file created with:
  - Vulnerability reporting URL or email
  - Expected response time
  - PGP key fingerprint (if using email)
  - Scope of covered versions
  - Link to the process for public disclosure after fix
- [ ] Email forwarding or ticket system tested (confirm message delivery)
- [ ] Named security contact identified in MAINTAINERS.md or SECURITY.md
- [ ] First-run test: send a test report and confirm human receipt within 24h

**Test:** Email sent to vulnerability contact is received and acknowledged

---

### REL-003: Supported Host/Executor Matrix

**Completion requires:**

For **each declared combination** (minimum: 1 Linux + Python + tmux + executor):

- [ ] Live environment provision (clean VM or container, no development files)
- [ ] Install from released artifact (wheel or source tarball, not git clone)
- [ ] Run acceptance test suite: `pytest tests/installed/ -v`
- [ ] Collect sealed evidence:
  - Test output (stdout/stderr)
  - Environment snapshot (uname, Python version, tmux version, executor version, API version)
  - Process traces (strace or similar if debugging required)
  - Git commit hash of test code (for reproducibility)
- [ ] Evidence archive created and uploaded to release artifacts
- [ ] COMPATIBILITY.md or section in TESTING.md updated with matrix results

**Test:** Acceptance tests pass on clean host; evidence is archived and referenced in release notes

---

### BKL-001: Durable Message Cursors (Depends on DEC-001)

**Completion requires (after DEC-001 decided):**

- [ ] Cursor storage mechanism implemented per DEC-001 (e.g., JSONL per consumer per workflow)
- [ ] Restart recovery tested: process restarts, cursor is resumed from last known position
- [ ] Duplicate safety tested: handler receives message twice (replay), disposition deduplicated correctly
- [ ] Cursor advancement tested: cursor only advances after successful handling (no race)
- [ ] Exit evidence: integration test in `tests/acceptance/test_message_cursor_lifecycle.py` passing
- [ ] Recorded in CHANGELOG.md and BACKLOG.md§BKL-001 moved to `done`

**Cross-reference:** OPERATIONS.md§durable-messages, BACKLOG.md§BKL-001

---

### BKL-002: Executor-Specific Post-Launch Steering (Depends on DEC-001)

**Completion requires (after DEC-001 decided):**

- [ ] Steering service accepts commands for running (non-restarted) executors
- [ ] Executor consumes steer without restart and emits `delivered`, `applied`, or `rejected` status
- [ ] Terminal text output is not accepted as proof (must be state-machine confirmation)
- [ ] Exit evidence: journey test in `tests/future/test_late_steering_journey.py` passing
- [ ] Recorded in CHANGELOG.md and BACKLOG.md§BKL-002 moved to `done`

**Cross-reference:** BACKLOG.md§BKL-002

---

## Resolution Order and Parallelization

### Phase 1: Decisions (Critical Path, ~1-2 weeks)

**Sequence (dependencies required):**

1. **REL-001 (License)** — independent, fast-track
   - Decision: internal maintainer call
   - Action: select license, update repo
   - Effort: 2-4h

2. **DEC-001 (Durable-control service objectives)** — independent but blocks BKL-001 & BKL-002
   - Decision: design workshop or ADR
   - Action: record decision, reference in BACKLOG.md
   - Effort: 4-8h
   - **Blocks:** BKL-001, BKL-002 exit evidence

3. **REL-002 (Vulnerability reporting)** — independent, external coordination
   - Decision: channel + contact process
   - Action: set up email/form, create SECURITY.md
   - Effort: 4-8h (can proceed in parallel with DEC-001 & REL-001)

### Phase 2: Execution (Parallelizable, ~2-3 weeks)

**After Phase 1 decisions, these can proceed in parallel:**

4. **REL-003 (Live compatibility testing)** — independent
   - Effort: 8-16h per platform (e.g., 3 platforms = 24-48h total, parallelizable)
   - Can begin as soon as release candidate branch exists

5. **BKL-001 (Durable cursors)** — blocks after DEC-001 decided
   - Effort: 8-16h
   - Can begin once DEC-001 is recorded

6. **BKL-002 (Post-launch steering)** — blocks after DEC-001 decided
   - Effort: 8-16h
   - Can begin once DEC-001 is recorded (may be parallelizable with BKL-001)

---

## Recommendations

### Immediate actions (this week)

1. **Schedule a 1-hour decision workshop** for DEC-001 (durable-control service objectives)
   - Invite: maintainer(s), ops/runtime owner (if separate)
   - Output: ADR or decision record with all five attributes filled
   - Action: commit to BACKLOG.md

2. **License decision** (can precede or follow workshop)
   - Review Apache 2.0 vs. MIT vs. AGPL trade-offs for this project
   - Confirm with legal/compliance if applicable
   - Commit license file and update `pyproject.toml`

3. **Assign vulnerability reporting** to security or ops lead
   - Determine monitored channel (email alias, security.txt, GitHub private reporting)
   - Create SECURITY.md template and first-run test plan

### Next actions (after Phase 1 decisions)

4. **Parallelize execution work:**
   - Assign a 3-person team to live compatibility testing (one per platform)
   - Assign implementation owners to BKL-001 and BKL-002
   - Each stream targets completion by <DATE>

5. **Release readiness gates:**
   - Before release: all P0 blockers in `done` state or decision recorded
   - Build candidate: `pytest && ./scripts/release-check.sh && python -m build`
   - Release: version bump + tag + signed release notes + evidence archive

---

## Risk Summary

| Risk | Impact | Mitigation |
|---|---|---|
| DEC-001 blocks BKL-001/002; late decision delays release 2+ weeks | High | Schedule workshop within 3 days |
| REL-003 (platform testing) is time-consuming and may surface bugs | Medium | Run live tests in parallel; use representative subset (1-2 Linux, 1 Python, 1 executor combo minimum) |
| REL-002 (vulnerability channel) requires real infrastructure | Medium | Confirm email/form delivery in dry run; plan 1-day buffer for setup |
| License choice is politically sensitive (GPL vs. permissive) | Medium | Align with project goals early; document rationale in commit message |

---

## Appendix: Reference Links

- **BACKLOG.md** — Task register with stable IDs and exit evidence
- **PUBLIC_RELEASE_READINESS.md** — Public release readiness criteria
- **TESTING.md** — Testing strategy and live compatibility lane
- **OPERATIONS.md** — Operational constraints and durable-message behavior
- **SECURITY.md** — (To be created; vulnerability reporting policy)
- **ARCHITECTURE.md** — System design and durable-control assumptions

---

**Document Owner:** Release Lead  
**Last Updated:** 2026-07-25  
**Next Review:** After DEC-001 decision
