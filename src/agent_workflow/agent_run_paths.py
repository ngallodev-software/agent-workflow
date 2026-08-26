from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentRunPaths:
    """Canonical run-local artifact paths.

    The immutable Agent Run contract still records the public path contract.
    This value object only removes duplicated filename knowledge from runtime
    code; it is not a second persistence authority.
    """

    root: Path

    @property
    def preflight(self) -> Path:
        return self.root / "preflight.json"

    @property
    def status(self) -> Path:
        return self.root / "status.json"

    @property
    def contract(self) -> Path:
        return self.root / "agent-run-contract.json"

    @property
    def command(self) -> Path:
        return self.root / "command.json"

    @property
    def prompt(self) -> Path:
        return self.root / "prompt.md"

    @property
    def launch_prompt(self) -> Path:
        return self.root / "launch-prompt.md"

    @property
    def output_log(self) -> Path:
        return self.root / "output.log"

    @property
    def completion_markdown(self) -> Path:
        return self.root / "completion.md"

    @property
    def completion(self) -> Path:
        return self.root / "completion.json"

    @property
    def result(self) -> Path:
        return self.root / "result.json"

    @property
    def provenance(self) -> Path:
        return self.root / "run-provenance.json"

    @property
    def source_baseline(self) -> Path:
        return self.root / "source-baseline.json"

    @property
    def evaluation_runtime(self) -> Path:
        return self.root / "evaluation-runtime.json"

    @property
    def workflow_inputs(self) -> Path:
        return self.root / "workflow-inputs.json"

    @property
    def job_binding(self) -> Path:
        return self.root / "job-binding.json"

    @property
    def agent_context(self) -> Path:
        return self.root / "agent-context.json"

    @property
    def executor_events(self) -> Path:
        return self.root / "executor-events.jsonl"

    @property
    def executor_stderr(self) -> Path:
        return self.root / "executor-stderr.log"


    @property
    def control_intents(self) -> Path:
        return self.root / "control-intents.jsonl"

    @property
    def repository_closeout(self) -> Path:
        return self.root / "repository-closeout.json"

    @property
    def process_result(self) -> Path:
        return self.root / "process-result.json"

    @property
    def provider_evidence(self) -> Path:
        return self.root / "provider-evidence.json"

    @property
    def patch(self) -> Path:
        return self.root / "patch.diff"

    @property
    def final_status(self) -> Path:
        return self.root / "final-status.json"

    @property
    def final_receipt(self) -> Path:
        return self.root / "final-receipt.json"

    @property
    def heartbeat(self) -> Path:
        return self.root / "heartbeat.json"

    @property
    def lifecycle_events(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def health_samples(self) -> Path:
        return self.root / "run-health-samples.jsonl"

    @property
    def permission_events(self) -> Path:
        return self.root / "permission-events.jsonl"

    @property
    def incident_events(self) -> Path:
        return self.root / "incident-events.jsonl"

    @property
    def remediation_events(self) -> Path:
        return self.root / "remediation-events.jsonl"

    @property
    def collections(self) -> Path:
        return self.root / "collections"

    @property
    def scope(self) -> Path:
        return self.root / "scope"

    @property
    def jobs(self) -> Path:
        return self.root / "jobs"

    @property
    def native_job(self) -> Path:
        return self.jobs / "native-job.json"

    def collection(self, name: str) -> Path:
        return self.collections / name
