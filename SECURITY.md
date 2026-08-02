# Security policy

## Supported versions

`agent-workflow` is pre-public-release software. Security fixes are applied to the current development line; older snapshots are not promised security support.

## Reporting a vulnerability

Do **not** open a public issue, discussion, or pull request containing vulnerability details.

The selected primary reporting channel is **GitHub Private Vulnerability Reporting** for the canonical public repository. Use the repository's **Security → Advisories → Report a vulnerability** action. If that action is unavailable, do not disclose details publicly; contact a repository administrator through an already established private channel and ask them to enable private vulnerability reporting or open a draft security advisory.

No project security email address is published until a monitored alias and response owner actually exist. The project will not invent an address or imply monitoring that has not been provisioned.

## What to include

Provide the affected version or revision, impact, reproduction steps, relevant environment details, and any proposed mitigation. Remove credentials, proprietary source, and unrelated personal data.

## Response policy

A repository administrator must enable private vulnerability reporting and complete a notification drill before the public-preview gate may pass. Incoming reports should be acknowledged, triaged, discussed, fixed, and disclosed through a private repository security advisory. Timelines depend on severity and reproducibility; the project does not promise a response SLA before a named response rotation exists.

## Scope boundary

Reports about dependency vulnerabilities should identify the dependency and affected version. Reports about unsafe prompts or model behavior should demonstrate a violation of an enforced authority, path, process, evidence, identity, or release boundary; model output that is merely low quality is not by itself a security vulnerability.
