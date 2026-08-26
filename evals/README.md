# Local evaluation assets

`fixtures/public` contains development fixtures, task text, and public acceptance checks. It contains no hidden oracle, canary, or reference patch. Resolve those after agent exit from `$AGENT_WORKFLOW_ORACLE_ROOT/<oracle-id>/oracle.json` and verify the SHA-256 declared by the evaluation dataset.

The no-op version of each fixture intentionally fails its public check. Inspect evaluation must copy fixture content into its Docker sandbox; never bind-mount the host checkout, home, workflow state, Docker socket, or oracle root.

The development dataset pins the SHA-256 of each external `oracle.json`. Those manifests declare only the public writable path; each external oracle directory must additionally contain a unique non-empty `canary.txt` plus any hidden checks/reference patch. The canary is scanned only after execution and must not appear in any sealed agent artifact.

## Primary-skill behavioral contract

`skills/agent-workflow/SKILL.md` is also checked against the deterministic scenario corpus in `evals/skills/agent-workflow.json`. These cases protect Phase 3's agent-facing decision boundaries without an LLM-as-judge release dependency or a parallel lifecycle schema. The release asset audit verifies that the primary skill continues to teach each required behavior; executable shell examples are independently checked against the live CLI parser.
