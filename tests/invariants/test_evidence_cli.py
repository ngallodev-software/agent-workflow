"""Standalone evidence manifest acceptance tests (run at end of phase)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[2] / "tools" / "evidence_cli.py"
spec = importlib.util.spec_from_file_location("evidence_cli", MODULE)
assert spec and spec.loader
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def test_capture_verify_and_inspect(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "sample.txt").write_bytes(b"hello")
    manifest = tmp_path / "evidence.json"
    assert evidence.main(["capture", str(root), str(manifest)]) == 0
    assert evidence.main(["verify", str(root), str(manifest)]) == 0
    assert evidence.main(["inspect", str(manifest)]) == 0
    assert '"count": 1' in capsys.readouterr().out


def test_mutation_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "sample.txt").write_bytes(b"hello")
    manifest = tmp_path / "evidence.json"
    assert evidence.main(["capture", str(root), str(manifest)]) == 0
    (root / "sample.txt").write_bytes(b"HELLO")
    assert evidence.main(["verify", str(root), str(manifest)]) == 1


def test_symlink_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "link").symlink_to(tmp_path)
    with pytest.raises(evidence.EvidenceError):
        evidence.capture(root)


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "a/../b", "a//b", "a/./b", "a\\b"])
def test_bad_paths(path: str) -> None:
    with pytest.raises(evidence.EvidenceError):
        evidence._path(path)


def test_manifest_rejects_duplicate_and_extra_fields(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    entry = {"path": "a", "size": 1, "sha256": "0" * 64}
    manifest.write_text(json.dumps({"schema": evidence.SCHEMA, "artifacts": [entry, entry]}))
    with pytest.raises(evidence.EvidenceError):
        evidence._load(manifest)
    manifest.write_text(json.dumps({"schema": evidence.SCHEMA, "artifacts": [{**entry, "unexpected": True}]}))
    with pytest.raises(evidence.EvidenceError):
        evidence._load(manifest)
