from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.receipts import make_read_only, seal_run, verify_seal
from agent_workflow.util import sha256_file
from tests.support import write_minimal_run


def test_sealed_receipt_rejects_tampering_and_path_redirection_matrix(tmp_path: Path) -> None:
    cases = ("artifact", "receipt", "intermediate-symlink")
    for case in cases:
        root = tmp_path / case
        write_minimal_run(root, session_id=case)
        seal_run(root, session_id=case)
        expected = sha256_file(root / "final-receipt.json")
        if case == "artifact":
            os.chmod(root / "output.log", 0o644)
            (root / "output.log").write_text("forged\n", encoding="utf-8")
        elif case == "receipt":
            os.chmod(root / "final-receipt.json", 0o644)
        else:
            original = root / "collections"
            target = root / "collections-real"
            original.rename(target)
            os.symlink(target.name, original)
        with pytest.raises(WorkflowError):
            verify_seal(root, expected_sha256=expected)


def test_sealing_rejects_unsafe_roots_and_incomplete_contracts(tmp_path: Path) -> None:
    unsafe = tmp_path / "unsafe"
    write_minimal_run(unsafe)
    target = unsafe / "outside"
    target.touch()
    os.symlink(target, unsafe / "seal.lock")
    with pytest.raises(WorkflowError):
        seal_run(unsafe, session_id="unsafe")

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "prompt.md").write_text("task\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="missing artifacts"):
        seal_run(incomplete, session_id="incomplete")


def test_read_only_transition_covers_optional_evidence_without_following_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "run"
    assignment = root / "assignments" / "child" / "record.json"
    assignment.parent.mkdir(parents=True)
    assignment.write_text("{}\n", encoding="utf-8")
    make_read_only(root)
    assert assignment.stat().st_mode & 0o222 == 0

    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    root2 = tmp_path / "run2"
    (root2 / "assignments").mkdir(parents=True)
    os.symlink(outside, root2 / "assignments" / "linked.json")
    before = outside.stat().st_mode
    with pytest.raises(WorkflowError, match="symlink"):
        make_read_only(root2)
    assert outside.stat().st_mode == before


def test_json_pointer_binding_subset_rejects_ambiguous_or_invalid_paths() -> None:
    from agent_workflow.bindings import resolve_json_pointer

    document = {"items": [{"id": "a"}], "a/b": {"~key": 3}}
    assert resolve_json_pointer(document, "/items/0/id") == "a"
    assert resolve_json_pointer(document, "/a~1b/~0key") == 3
    with pytest.raises(WorkflowError, match="invalid escape"):
        resolve_json_pointer(document, "/bad~2escape")
    with pytest.raises(WorkflowError, match="start with"):
        resolve_json_pointer(document, "items/0")
