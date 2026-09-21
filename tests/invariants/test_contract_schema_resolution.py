from __future__ import annotations

import json
from pathlib import Path

from agent_workflow import contracts


def _write_schema(root: Path, *, accepts_criteria: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    properties = {"criteria": {"type": "array"}} if accepts_criteria else {}
    (root / "agent-run-contract.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": contracts.AGENT_RUN_CONTRACT_SCHEMA,
                "type": "object",
                "properties": properties,
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )


def test_active_prefix_schema_beats_stale_user_data(
    tmp_path: Path, monkeypatch
) -> None:
    prefix = tmp_path / "venv"
    module_path = (
        prefix
        / "lib"
        / "python3.11"
        / "site-packages"
        / "agent_workflow"
        / "contracts.py"
    )
    module_path.parent.mkdir(parents=True)

    installed_root = prefix / "share" / "agent-workflow" / "schemas"
    user_data_home = tmp_path / "user-share"
    stale_user_root = user_data_home / "agent-workflow" / "schemas"
    _write_schema(installed_root, accepts_criteria=True)
    _write_schema(stale_user_root, accepts_criteria=False)

    monkeypatch.setattr(contracts, "__file__", str(module_path))
    monkeypatch.setattr(contracts.sys, "prefix", str(prefix))
    monkeypatch.setenv("XDG_DATA_HOME", str(user_data_home))
    contracts._schema_index.cache_clear()
    try:
        assert contracts._schema_roots() == (installed_root,)
        contracts.validate_instance(
            {"criteria": []},
            contracts.AGENT_RUN_CONTRACT_SCHEMA,
            artifact="fresh-agent-run-contract",
        )
    finally:
        contracts._schema_index.cache_clear()


def test_user_install_schema_beats_system_prefix_data(
    tmp_path: Path, monkeypatch
) -> None:
    prefix = tmp_path / "system-prefix"
    module_path = (
        tmp_path
        / "home"
        / ".local"
        / "lib"
        / "python3.11"
        / "site-packages"
        / "agent_workflow"
        / "contracts.py"
    )
    module_path.parent.mkdir(parents=True)

    stale_system_root = prefix / "share" / "agent-workflow" / "schemas"
    user_data_home = tmp_path / "home" / ".local" / "share"
    user_root = user_data_home / "agent-workflow" / "schemas"
    _write_schema(stale_system_root, accepts_criteria=False)
    _write_schema(user_root, accepts_criteria=True)

    monkeypatch.setattr(contracts, "__file__", str(module_path))
    monkeypatch.setattr(contracts.sys, "prefix", str(prefix))
    monkeypatch.setenv("XDG_DATA_HOME", str(user_data_home))
    contracts._schema_index.cache_clear()
    try:
        assert contracts._schema_roots() == (user_root,)
        contracts.validate_instance(
            {"criteria": []},
            contracts.AGENT_RUN_CONTRACT_SCHEMA,
            artifact="user-agent-run-contract",
        )
    finally:
        contracts._schema_index.cache_clear()
