from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.evidence_repair import (
    ADAPTER_ID,
    create_evidence_repair,
    list_evidence_repairs,
    supplemental_repairs_for_run,
    verify_evidence_repair,
)
from agent_workflow.receipts import final_receipt_sha256, make_read_only, seal_run
from agent_workflow.util import atomic_write_json
from tests.support import write_minimal_run


def _settings(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = tmp_path / "config.toml"
    state_root = tmp_path / "state"
    worktree_root = tmp_path / "worktrees"
    config.write_text(
        "schema_version = 1\n\n"
        "[paths]\n"
        f"state_root = {json.dumps(str(state_root))}\n"
        f"worktree_root = {json.dumps(str(worktree_root))}\n",
        encoding="utf-8",
    )
    state_root.mkdir(mode=0o700)
    worktree_root.mkdir(mode=0o700)
    return replace(defaults(config), state_root=state_root, worktree_root=worktree_root)


def _legacy_completion(session_id: str, *, malformed_command: bool = False) -> dict:
    return {
        "schema": "tax-machine/completion/v0",
        "session_id": session_id,
        "ticket_id": "P1-REV-001",
        "pack_id": "tax-machine-backlog-v1",
        "result": "changes_requested",
        "disposition": "changes_requested",
        "base_revision": "base",
        "head_revision": "head",
        "changed_files": [],
        "criteria": [{"id": "review", "result": "fail", "evidence": ["durability gap"]}],
        "commands": [
            {
                "argv": "pytest -q" if malformed_command else ["pytest", "-q"],
                "cwd": "/repo",
                "exit_code": 0,
                "receipt": "1 passed",
            }
        ],
        "unresolved": ["durability gap"],
        "usage": None,
    }


def _sealed_source(tmp_path: Path, *, malformed_command: bool = False):
    settings = _settings(tmp_path)
    session_id = "source-review-run"
    run = settings.state_root / "runs" / session_id
    write_minimal_run(run, session_id=session_id)
    atomic_write_json(run / "result.json", _legacy_completion(session_id, malformed_command=malformed_command))
    seal_run(run, session_id=session_id)
    make_read_only(run)
    return settings, run, final_receipt_sha256(run)


def _create(settings, digest: str, *, repair_id: str = "review-repair-1"):
    return create_evidence_repair(
        settings,
        source_session_id="source-review-run",
        source_receipt_sha256=digest,
        source_artifact_path="result.json",
        adapter=ADAPTER_ID,
        output_run=repair_id,
        actor="coordinator",
    )


def test_evidence_repair_rejects_untrusted_bindings_paths_and_invented_command_evidence(
    tmp_path: Path,
) -> None:
    settings, _run, digest = _sealed_source(tmp_path / "bindings")
    attempts = [
        {
            "receipt": "0" * 64,
            "artifact": "result.json",
            "repair": "wrong-receipt",
            "match": "checksum mismatch",
        },
        *(
            {
                "receipt": digest,
                "artifact": unsafe,
                "repair": f"unsafe-{index}",
                "match": "normalized run-relative path|POSIX",
            }
            for index, unsafe in enumerate(
                ("../result.json", "/tmp/result.json", "nested/../result.json", r"nested\\result.json")
            )
        ),
    ]
    for attempt in attempts:
        with pytest.raises(WorkflowError, match=attempt["match"]):
            create_evidence_repair(
                settings,
                source_session_id="source-review-run",
                source_receipt_sha256=attempt["receipt"],
                source_artifact_path=attempt["artifact"],
                adapter=ADAPTER_ID,
                output_run=attempt["repair"],
                actor="coordinator",
            )
        assert not (settings.state_root / "evidence-repairs" / attempt["repair"]).exists()

    malformed_settings, _run, malformed_digest = _sealed_source(
        tmp_path / "malformed", malformed_command=True
    )
    with pytest.raises(WorkflowError, match="repaired canonical completion"):
        _create(malformed_settings, malformed_digest, repair_id="unsafe-normalization")
    assert not (
        malformed_settings.state_root / "evidence-repairs" / "unsafe-normalization"
    ).exists()


def test_evidence_repair_fails_closed_for_symlinks_and_tampering(tmp_path: Path) -> None:
    settings, run, digest = _sealed_source(tmp_path)
    root = settings.state_root / "evidence-repairs"
    root.mkdir(mode=0o700)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "symlink-repair").symlink_to(outside, target_is_directory=True)

    with pytest.raises(WorkflowError, match="not a regular directory"):
        _create(settings, digest, repair_id="symlink-repair")

    created = _create(settings, digest, repair_id="tampered-repair")
    repair = Path(created["repair_dir"])
    canonical = repair / "canonical-completion.json"
    os.chmod(canonical, 0o600)
    canonical.write_text("{}\n", encoding="utf-8")
    os.chmod(canonical, 0o400)

    with pytest.raises(WorkflowError, match="artifact changed"):
        verify_evidence_repair(settings, "tampered-repair")
    assert supplemental_repairs_for_run(run, digest) == []
    rows = list_evidence_repairs(settings, source_session_id="source-review-run")
    assert any(
        row["repair_id"] == "tampered-repair" and row["validation_result"] == "invalid"
        for row in rows
    )
