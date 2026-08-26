from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import InstalledProduct, git_repo


def test_installed_cli_records_failed_preflight_without_starting_worker(
    installed_product: InstalledProduct, product_env: dict[str, str], tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("preflight test\n", encoding="utf-8")
    result = installed_product.run(
        "agent-run", "prepare", "preflight-failure", repo, prompt,
        "--prerequisite", "missing-prerequisite", env=product_env,
    )
    assert result.returncode == 2
    assert "missing prerequisites" in result.stderr
    run = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / "preflight-failure"
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert status["failure_category"] == "preflight_failed"
    assert status["preflight"]["status"] == "missing"
    assert status.get("worker_id") is None
    assert status.get("worker_pid") is None
    assert not (run / "final-receipt.json").exists()
