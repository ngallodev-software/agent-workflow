import pytest

from agent_workflow.contracts import validate_job_binding
from agent_workflow.errors import WorkflowError


def test_job_binding_rejects_unsupported_schema() -> None:
    with pytest.raises(WorkflowError, match="unsupported job binding schema"):
        validate_job_binding({"schema": "agent-workflow/job-binding/v99"}, allow_dependent=True)


def test_job_binding_validates_supported_schema() -> None:
    with pytest.raises(WorkflowError, match="invalid job binding"):
        validate_job_binding({"schema": "agent-workflow/job-binding/v2"})
