# REL-008 — Cross-platform release installers

## Delegation metadata

- Ticket: `REL-008`
- Recommended tier: A
- Dependencies: none
- New terminal session required: yes
- Implementation risk: high

## Objective

Verify and harden the implemented release-install surface for Linux, Windows through WSL2, and macOS without broadening its support claims.

## Required reading

- repository root README and package metadata;
- `install.sh`, `uninstall.sh`, package metadata, and current GitHub workflows;
- `EXECUTION_PROTOCOL.md`;
- relevant included references.

## Writable paths

`install.sh`, `uninstall.sh`, a curl-bootstrap entry point, GitHub release workflow,
release-bundle scripts/templates, tests, and installation/release documentation.

## Procedure

1. Perform the exact-worktree preflight before source discovery.
2. Add a small POSIX curl bootstrap script usable as
   `curl -fsSL https://github.com/ngallodev-software/agent-workflow/raw/<tag>/install.sh | sh`.
   It must reject unsupported OS/architecture, require a supported Python, verify
   release artifact checksums, and never execute a mutable default branch URL.
3. Make Linux, WSL2, and macOS use the same wheel-based release contract; WSL2
   is Linux after explicit detection/documentation. Native Windows remains out of scope.
4. Add deterministic GitHub release automation that builds wheel/sdist, checksum
   manifest, platform-labelled installer bundles (`linux`, `wsl2`, `macos`), and
   uploads them only for a version tag. Do not publish a release from pull requests.
5. Keep MCP as an explicit optional install profile; normal installation must not register MCP or require its SDK.
6. Add inventory tests proving Jenkinsfile, Jenkins server-job files, and `.github/workflows/` are absent from wheels and runtime bundles.
7. Add offline/fake-download tests for selector, checksum, and unsupported-host
   behavior plus workflow/bundle validation. Document curl install, bundle install,
   uninstall, Python requirements, and trust boundary.

## Acceptance criteria

- immutable tag/version artifact selection is required;
- checksum failure stops before install;
- Linux, WSL2, and macOS bundles contain their needed bootstrap files;
- release automation cannot publish untagged builds;
- base installation succeeds without MCP and the optional MCP profile remains explicit;
- repository-only Jenkins/GitHub workflow assets are absent from installed wheels and runtime bundles;
- installed executable is verified by a black-box journey.

## Necessary tests

Run focused installer tests, release workflow/static validation, package build,
and an installed-product journey. Retain no network-dependent test.

## Stop and escalate conditions

Stop if a trustworthy immutable release reference or checksum contract cannot be
established. Do not claim native Windows support or publish a real GitHub release.

## Required completion report

Use `templates/TICKET_COMPLETION.md` with committed revision-bound evidence.
