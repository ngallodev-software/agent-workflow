from pathlib import Path

from agent_workflow.config import defaults
from agent_workflow.delegation import _delegation_result


def test_external_launch_contract_includes_durable_delivery_commands(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "state_root", tmp_path / "state")
    result = _delegation_result(
        settings=settings,
        agent_run_id="run-1",
        worktree=tmp_path / "worktree",
        role="implementation",
        worker_mode="external",
        state="prepared",
        reused_existing_run=False,
        worktree_created=False,
    )
    launch = result["launch_contract"]
    assert "pending-external-delivery run-1 --generation GENERATION" in launch["pending_delivery_command"]
    assert "report-external-delivery run-1 MESSAGE_ID" in launch["report_delivery_command"]
