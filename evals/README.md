# Local evaluation assets

`fixtures/public` contains development fixtures, task text, and public acceptance checks. It contains no hidden oracle, canary, or reference patch. Resolve those after agent exit from `$AGENT_WORKFLOW_ORACLE_ROOT/<oracle-id>/oracle.json` and verify the SHA-256 declared by the evaluation dataset.

The no-op version of each fixture intentionally fails its public check. Inspect evaluation must copy fixture content into its Docker sandbox; never bind-mount the host checkout, home, workflow state, Docker socket, or oracle root.

The development dataset pins the SHA-256 of each external `oracle.json`. Those manifests declare only the public writable path; each external oracle directory must additionally contain a unique non-empty `canary.txt` plus any hidden checks/reference patch. The canary is scanned only after execution and must not appear in any sealed agent artifact.
