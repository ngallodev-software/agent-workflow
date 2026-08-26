from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agent_workflow.manifests import ValidationReport, _load_yaml


def test_manifest_yaml_uses_safe_loader_and_rejects_python_tags(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    path = root / "pack.yaml"
    path.write_text("value: !!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8")
    report = ValidationReport(root=root)

    assert _load_yaml(path, report) is None
    assert report.errors
    assert "invalid YAML" in report.errors[0]


def test_manifest_yaml_supports_standard_nested_yaml(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    path = root / "pack.yaml"
    path.write_text(
        "phase: '0'\n"
        "tasks:\n"
        "  - id: TASK-001\n"
        "    dependencies:\n"
        "      - BASE-001\n"
        "    result_contract:\n"
        "      schema: example/v1\n",
        encoding="utf-8",
    )
    report = ValidationReport(root=root)

    value = _load_yaml(path, report)

    assert report.ok
    assert value == {
        "phase": "0",
        "tasks": [
            {
                "id": "TASK-001",
                "dependencies": ["BASE-001"],
                "result_contract": {"schema": "example/v1"},
            }
        ],
    }


def test_pyyaml_safe_load_does_not_construct_python_objects() -> None:
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load("!!python/object/new:tuple [[1, 2]]")
