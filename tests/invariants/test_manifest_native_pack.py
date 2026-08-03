from __future__ import annotations

import json
from pathlib import Path

from agent_workflow.manifests import validate_pack


def _write_pack(root: Path, *, schema: str = "agent-workflow/manifest-native-pack/v1") -> None:
    (root / "tickets").mkdir(parents=True)
    for ticket in ("T-1", "T-2"):
        (root / "tickets" / f"{ticket}.md").write_text(
            "Writable scope, acceptance criteria, tests, and stop conditions.\n",
            encoding="utf-8",
        )
    (root / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema": schema,
                "pack_id": "native-pack",
                "tickets": [
                    {"id": "T-1", "prompt": "tickets/T-1.md", "dependencies": []},
                    {"id": "T-2", "prompt": "tickets/T-2.md", "dependencies": ["T-1"]},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_manifest_native_pack_rejects_unknown_schemas_and_dependency_cycles(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown"
    _write_pack(unknown, schema="agent-workflow/manifest-native-pack/v99")
    report = validate_pack(unknown)
    assert not report.ok
    assert any("unsupported manifest schema" in error for error in report.errors)

    cyclic = tmp_path / "cyclic"
    _write_pack(cyclic)
    manifest = json.loads((cyclic / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest["tickets"][0]["dependencies"] = ["T-2"]
    (cyclic / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = validate_pack(cyclic)
    assert not report.ok
    assert "dependency cycle: T-1 -> T-2 -> T-1" in report.errors
