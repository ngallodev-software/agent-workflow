from pathlib import Path

from agent_workflow import delegation
from agent_workflow.config import defaults


def test_external_launch_contract_includes_durable_delivery_commands(
    tmp_path: Path, monkeypatch
) -> None:
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "state_root", tmp_path / "state")
    handoff = settings.state_root / "runs" / "run-1" / "handoff"
    monkeypatch.setattr(
        delegation,
        "read_agent_run_contract",
        lambda _path: {"paths": {"handoff_dir": str(handoff)}},
    )

    result = delegation._delegation_result(
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
    assert launch["launch_prompt_path"] == str(
        settings.state_root / "runs" / "run-1" / "launch-prompt.md"
    )
    assert launch["handoff_dir"] == str(handoff)
    assert launch["completion_template_path"] == str(handoff / "completion-template.json")
    assert "pending-external-delivery run-1 --generation GENERATION" in launch["pending_delivery_command"]
    assert "report-external-delivery run-1 MESSAGE_ID" in launch["report_delivery_command"]
