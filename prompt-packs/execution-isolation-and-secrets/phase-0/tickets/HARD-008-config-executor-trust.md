# HARD-008 — configuration and executor trust

**Backlog:** [`HARD-008`](../../../../BACKLOG.md)  
**Priority:** P1 / High  
**Assessment:** [F03-F06, F15, and F20](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#41-entry-points-configuration-host-integration-and-release-tooling) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Treat configuration, executable resolution, and compatibility data as deterministic policy inputs with ownership checks and provenance rather than ambient host assumptions.

## Current risk

The current TOML/default model can accept unknown or weakly protected policy data, PATH resolution is not a durable identity, Git/executor behavior can inherit unsafe environment or repository configuration, and supported adapter versions are not a release-backed contract.

## Required implementation

- Add a versioned configuration schema, reject unknown policy keys, and distinguish user settings from shipped compatibility data.
- Check owner and group/world-writable modes for config, state root, repository allowlists, and policy files. Define warnings versus hard failures for local development and governed/release modes.
- Resolve named executors to an explicit path, probe version/capabilities through HARD-001, and record path/version/adapter version/optional digest in launch provenance and doctor output.
- Sanitize Git and executor environments: disable pagers/external diff where appropriate, avoid shell aliases, and document repository hooks/filters trust. Do not break intentional repository behavior silently; expose a policy decision.
- Move changing executor/model compatibility information into a versioned data surface with explanation codes. Keep no-go enforcement server-side.
- Add a dry-run/doctor view showing the exact policy, executable, and compatibility decision without exposing credentials.

## Writable paths

- src/agent_workflow/config.py, doctor.py, executors.py, git.py, sessions identity/provenance, packaged compatibility assets
- config schema and example
- installed-product config/doctor/launch journeys and compact mode/unknown-key matrix
- docs/INSTALLATION.md, OPERATIONS.md, SECURITY.md, TESTING.md

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

External prerequisite: FOUND-GATE-01 accepted. Within this pack it runs first and is a dependency of HARD-003 and HARD-006.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- A clean isolated HOME loads a valid config and reports resolved executable identity and adapter compatibility.
- Unknown policy keys and group/world-writable governed config fail with stable remediation; local warning behavior is explicit and tested.
- A PATH substitution between doctor and launch is detected or the launch provenance records the actual executable used.
- Git operations are not changed by aliases/pagers and do not leak inherited credential-agent variables.
- Unsupported adapter versions fail clearly and do not silently downgrade to unclassified governed execution.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- Configuration is executable policy and must be root-contained and no-follow read.
- Executable identity evidence must come from the actual path launched.
- No secrets in config examples, doctor output, provenance, or errors.

## Non-targets

- Do not implement the OS sandbox owned by HARD-003.
- Do not add online capability discovery, autonomous model selection, or remote config service.
- Do not run paid provider tasks in the default suite.

## Stop conditions

- HARD-001 foundation is not accepted.
- A compatibility rule requires an unsupported current-provider fact with no pinned source/evidence.
- Mode enforcement would lock users out without a documented migration/remediation path.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
