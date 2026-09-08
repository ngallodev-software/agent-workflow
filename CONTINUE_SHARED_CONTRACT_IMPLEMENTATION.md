# Continue shared SpecGen and Agent-Workflow contract implementation

Continue the shared SpecGen to Agent-Workflow contract implementation until all
remaining accepted requirements are complete.

Start by reading the canonical spec, generated pack, GIT-LEASE-001
implementation brief, both backlogs, and current Git status in:

- `/lump/apps/specgen-aw`
- `/lump/apps/agent-workflow`
- `/lump/apps/agent-workflow-spec-contracts`

Use Agent-Workflow durable Agent Runs for delegated engineering. Treat worker
exit, completion, evaluation, review, and acceptance as separate gates. Poll
active runs every 60 seconds with `agent-workflow supervisor run
--interval-seconds 60` or targeted status checks.

Do not stop at partial worker output. Independently verify every recovered or
integrated change, run applicable tests/build/wheel-install checks, and commit
only validated repository-owned changes. Preserve sealed evidence and never
alter historical artifacts.

Priority order:

1. Finish and verify GIT-LEASE-001: fail before launch when Git administrative
   storage is not writable; reject completion revisions absent from repository
   object storage.
2. Add and verify the documented coordinator-commit fallback if direct worker
   commits remain impossible.
3. Run installed-wheel producer to SpecGen v2 pack to Agent-Workflow
   validation, including exact match, version/digest mismatch rejection, v1 to
   v2 migration, unsupported migration failure, and sealed-input preservation.
4. Independently review all phases; update durable findings/backlogs with
   errors, weaknesses, and follow-ups.
5. Build, install, test, commit, then report only what is actually verified.

Do not publish externally. If blocked by required authority or an unrecoverable
environment limitation, record exact evidence and continue every safe in-scope
diagnostic/remediation path before asking for direction.
