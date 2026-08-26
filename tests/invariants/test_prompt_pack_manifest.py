from __future__ import annotations

from pathlib import Path

import yaml

from agent_workflow.manifests import validate_pack
from agent_workflow.pack import scaffold


def _manifest(root: Path) -> dict:
    value = yaml.safe_load((root / "pack.yaml").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_prompt_pack_rejects_unknown_schema_and_dependency_cycles(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown"
    scaffold(unknown, 1, "unknown")
    manifest = _manifest(unknown)
    manifest["schema"] = "agent-workflow/prompt-pack/v99"
    (unknown / "pack.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    report = validate_pack(unknown)
    assert not report.ok
    assert any("prompt-pack/v1" in error or "const" in error for error in report.errors)

    cyclic = tmp_path / "cyclic"
    scaffold(cyclic, 2, "cyclic")
    manifest = _manifest(cyclic)
    first = manifest["phases"][0]["tasks"][0]
    second = manifest["phases"][1]["tasks"][0]
    first["dependencies"] = [second["id"]]
    second["dependencies"] = [first["id"]]
    (cyclic / "pack.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    report = validate_pack(cyclic)
    assert not report.ok
    assert "dependency cycle: P0-00 -> P1-00 -> P0-00" in report.errors
