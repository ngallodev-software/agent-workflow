from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import InstalledProduct


def test_installed_product_can_install_and_verify_hierarchy_contracts(
    installed_product: InstalledProduct,
    tmp_path: Path,
) -> None:
    root = tmp_path / "hierarchy"
    script = r'''
import json
import sys
from pathlib import Path
from agent_workflow.hierarchy import (
    install_contract_set,
    read_contract_set,
    seal_hierarchy_contract,
    seal_team_delegation_contract,
)

root = Path(sys.argv[1])
digest = "sha256:" + "b" * 64
hierarchy = seal_hierarchy_contract({
    "schema": "agent-workflow/orchestration-hierarchy/v1",
    "version": 1,
    "orchestration_id": "installed-root",
    "root_orchestrator_id": "installed-orchestrator",
    "workflow_id": "installed-workflow",
    "allowed_depth": 2,
    "tmux_session_name": "installed-tmux",
    "budgets": {
        "max_teams": 1,
        "max_total_workers": 4,
        "max_concurrent_workers": 2,
        "max_interactive_panes": 5,
        "max_retries_per_worker": 1,
        "max_wall_seconds": 3600,
    },
    "terminal_policy": {"allowed_modes": ["current"], "external_argv_prefixes": []},
    "allowed": {
        "executors": ["codex"],
        "models": ["gpt-5.6"],
        "agent_classes": ["implementation"],
        "permissions": ["workspace-write"],
        "commands": ["run", "status"],
    },
    "allowed_routes": ["root-to-team", "team-to-root", "team-to-worker", "worker-to-team"],
    "teams": [{
        "team_id": "implementation",
        "team_lead_session_id": "installed-lead",
        "parent_principal": "root",
    }],
    "source": {
        "repository": "file:///installed-product",
        "revision": "abc123",
        "snapshot_sha256": digest,
        "prompt_pack_id": "hierarchical-multi-team-orchestration",
        "prompt_pack_sha256": digest,
    },
    "created_at": "2026-08-01T20:00:00+00:00",
})
team = seal_team_delegation_contract({
    "schema": "agent-workflow/team-delegation/v1",
    "version": 1,
    "orchestration_id": "installed-root",
    "root_orchestrator_id": "installed-orchestrator",
    "team_id": "implementation",
    "team_lead_session_id": "installed-lead",
    "objective": "Prove installed hierarchy authority",
    "deliverables": ["reports/result.json"],
    "writable_scope": ["work/implementation"],
    "no_go_scope": ["secrets"],
    "stop_conditions": ["authority mismatch"],
    "dependencies": [],
    "required_outputs": ["agent-workflow/task-result/v1"],
    "budgets": {
        "max_workers": 2,
        "max_concurrent_workers": 1,
        "max_interactive_panes": 3,
        "max_retries": 1,
        "max_wall_seconds": 1800,
    },
    "allowed": {
        "executors": ["codex"],
        "models": ["gpt-5.6"],
        "agent_classes": ["implementation"],
        "permissions": ["workspace-write"],
        "commands": ["run"],
    },
    "message_routes": ["team-to-root", "team-to-worker", "worker-to-team"],
    "required_reviews": ["independent"],
    "required_approvals": ["root-final"],
    "parent_action_cursor": 0,
}, hierarchy)
manifest = install_contract_set(root, hierarchy, (team,))
loaded_hierarchy, loaded_teams, loaded_manifest = read_contract_set(root)
print(json.dumps({
    "orchestration_id": loaded_hierarchy["orchestration_id"],
    "team_ids": [item["team_id"] for item in loaded_teams],
    "manifest_equal": manifest == loaded_manifest,
    "hierarchy_mode": oct((root / "hierarchy.json").stat().st_mode & 0o777),
}, sort_keys=True))
'''
    result = subprocess.run(
        [str(installed_product.python), "-c", script, str(root)],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "hierarchy_mode": "0o400",
        "manifest_equal": True,
        "orchestration_id": "installed-root",
        "team_ids": ["implementation"],
    }
