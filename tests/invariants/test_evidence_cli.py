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


def test_capture_never_overwrites_existing_manifest(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "data").write_bytes(b"data")
    manifest = tmp_path / "manifest.json"
    assert evidence.main(["capture", str(root), str(manifest)]) == 0
    original = manifest.read_bytes()
    assert evidence.main(["capture", str(root), str(manifest)]) == 1
    assert manifest.read_bytes() == original


def test_capture_rejects_manifest_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "data").write_bytes(b"data")
    assert evidence.main(["capture", str(root), str(root / "manifest.json")]) == 1


def test_extra_artifact_invalidates_manifest(tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "data").write_bytes(b"data")
    manifest = tmp_path / "manifest.json"
    assert evidence.main(["capture", str(root), str(manifest)]) == 0
    (root / "extra").write_bytes(b"extra")
    assert evidence.main(["verify", str(root), str(manifest)]) == 1


def test_command_receipt_bounded_stream_and_full_digest(tmp_path: Path) -> None:
    import hashlib
    import sys
    data = b"x" * 200000
    receipt = evidence.run_receipt(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x'*200000); sys.stderr.write('oops')"],
        tmp_path, timeout=10, max_bytes=32,
    )
    assert receipt["exit_code"] == 0
    assert receipt["stdout"]["size"] == len(data)
    assert receipt["stdout"]["sha256"] == hashlib.sha256(data).hexdigest()
    assert receipt["stdout"]["captured"] == "x" * 32
    assert receipt["stdout"]["truncated"] is True
    assert receipt["stderr"]["captured"] == "oops"


def test_command_timeout_and_no_overwrite(tmp_path: Path) -> None:
    import sys
    receipt = tmp_path / "run.json"
    command = ["run", "--cwd", str(tmp_path), "--receipt", str(receipt), "--timeout", "0.1", "--",
               sys.executable, "-c", "import time; time.sleep(10)"]
    assert evidence.main(command) == 124
    assert json.loads(receipt.read_text())["timed_out"] is True
    original = receipt.read_bytes()
    assert evidence.main(command) == 1
    assert receipt.read_bytes() == original


def test_verify_receipt_complete_output_and_tampering(tmp_path: Path) -> None:
    import sys
    receipt = tmp_path / "receipt.json"
    assert evidence.main(["run", "--cwd", str(tmp_path), "--receipt", str(receipt),
                          "--", sys.executable, "-c", "print('hello')"]) == 0
    assert evidence.main(["verify-receipt", str(receipt)]) == 0
    value = json.loads(receipt.read_text())
    value["stdout"]["captured"] = "altered"
    receipt.write_text(json.dumps(value))
    assert evidence.main(["verify-receipt", str(receipt)]) == 1


def test_verify_receipt_truncated_output_is_not_authenticated(tmp_path: Path) -> None:
    import sys
    receipt = tmp_path / "receipt.json"
    assert evidence.main(["run", "--cwd", str(tmp_path), "--receipt", str(receipt),
                          "--max-output-bytes", "4", "--",
                          sys.executable, "-c", "print('long output')"]) == 0
    result = evidence.verify_receipt(receipt)
    assert result["authenticated"] is False
    assert "stdout" not in result["complete_streams_verified"]
    value = json.loads(receipt.read_text())
    value["timed_out"] = True
    receipt.write_text(json.dumps(value))
    assert evidence.main(["verify-receipt", str(receipt)]) == 1
