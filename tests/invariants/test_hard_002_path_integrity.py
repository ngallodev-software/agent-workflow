from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

from agent_workflow.config import defaults
from agent_workflow.contracts import _schema_index, load_schema
from agent_workflow.errors import WorkflowError
from agent_workflow.manifests import validate_pack
from agent_workflow.native_jobs import validate_native_job
from agent_workflow.pack import archive, scaffold
from agent_workflow.path import inventory_tree, read_inventory_file


@pytest.mark.parametrize("entry_type", ["symlink", "fifo", "socket"])
def test_pack_validation_rejects_irregular_entries(tmp_path: Path, entry_type: str) -> None:
    pack = tmp_path / entry_type
    scaffold(pack, 1, entry_type)
    entry = pack / "rejected"
    if entry_type == "symlink":
        entry.symlink_to(pack / "README.md")
    elif entry_type == "fifo":
        os.mkfifo(entry)
    else:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(entry))
        except PermissionError:
            listener.close()
            pytest.skip("filesystem socket creation is not permitted")
    try:
        report = validate_pack(pack, verify_checksums=False)
        assert not report.ok
        assert "rejected" in report.errors[0]
    finally:
        if entry_type == "socket":
            listener.close()


def test_archive_is_reproducible_and_manifest_covers_validated_inventory(tmp_path: Path) -> None:
    pack = tmp_path / "valid"
    scaffold(pack, 1, "valid")
    first = tmp_path / "first.tar.zst"
    second = tmp_path / "second.tar.zst"
    archive(defaults(), pack, first)
    archive(defaults(), pack, second)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()


def test_pack_validation_treats_checksum_manifest_as_optional_transfer_state(tmp_path: Path) -> None:
    pack = tmp_path / "valid"
    scaffold(pack, 1, "valid")
    (pack / "MANIFEST.sha256").write_text("stale checksum\n", encoding="utf-8")

    assert validate_pack(pack).ok
    verified = validate_pack(pack, verify_checksums=True)
    assert not verified.ok
    assert any("MANIFEST.sha256" in error for error in verified.errors)


def test_archive_excludes_mutable_checksum_sidecar(tmp_path: Path) -> None:
    pack = tmp_path / "valid"
    scaffold(pack, 1, "valid")
    (pack / "MANIFEST.sha256").write_text("stale checksum\n", encoding="utf-8")
    output = tmp_path / "pack.tar.zst"
    archive(defaults(), pack, output)

    compressed = subprocess.run(["zstd", "-dc", str(output)], check=True, capture_output=True)
    listing = subprocess.run(
        ["tar", "-tf", "-"], input=compressed.stdout, check=True, capture_output=True
    ).stdout.decode("utf-8")
    assert "MANIFEST.sha256" not in listing
    assert "MANIFEST.json" in listing


def test_archive_rejects_a_replaced_entry_after_inventory(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    source = root / "source.txt"
    source.write_text("before", encoding="utf-8")
    entry = inventory_tree(root)[0]
    source.unlink()
    source.write_text("after", encoding="utf-8")
    with pytest.raises(WorkflowError, match="changed after validation"):
        read_inventory_file(root, entry)


def test_native_job_rejects_symlinked_job_and_prompt_components(tmp_path: Path) -> None:
    root = tmp_path / "pack"
    root.mkdir()
    (root / "work").mkdir()
    (root / "prompt.md").write_text("prompt", encoding="utf-8")
    job = {
        "schema": "agent-workflow/native-job/v1",
        "job_id": "job",
        "ticket_id": "ticket",
        "prompt_path": "prompt.md",
        "worktree_target": "work",
        "path_policy": {"allowed_paths": ["src"]},
        "acceptance_commands": [],
        "review_requirement": {"required": False},
    }
    (root / "job.json").write_text(json.dumps(job), encoding="utf-8")
    assert validate_native_job(root / "job.json", pack_root=root).prompt_bytes == b"prompt"
    (root / "linked-job.json").symlink_to(root / "job.json")
    with pytest.raises(WorkflowError):
        validate_native_job(root / "linked-job.json", pack_root=root)
    (root / "linked-prompt.md").symlink_to(root / "prompt.md")
    job["prompt_path"] = "linked-prompt.md"
    (root / "job.json").write_text(json.dumps(job), encoding="utf-8")
    with pytest.raises(WorkflowError, match="prompt_path"):
        validate_native_job(root / "job.json", pack_root=root)


def test_packaged_schema_authority_is_present_and_duplicate_ids_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert load_schema("agent-workflow/native-job/v1")["$id"] == "agent-workflow/native-job/v1"
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    schema = {"$id": "example.test/duplicate", "type": "object"}
    first.write_text(json.dumps(schema), encoding="utf-8")
    second.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr("agent_workflow.contracts._schema_roots", lambda: (tmp_path,))
    _schema_index.cache_clear()
    try:
        with pytest.raises(WorkflowError, match="duplicate packaged contract schema ID"):
            _schema_index()
    finally:
        _schema_index.cache_clear()
