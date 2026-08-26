from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.index_sources import (
    artifact_paths,
    discover_runs,
    read_stable_bytes,
    sha256_file,
    source_fingerprint,
)


def _settings(tmp_path: Path):
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "state_root", tmp_path / "state")
    return settings


def test_discovery_prefers_active_run_over_archive_duplicate(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    active = settings.state_root / "runs" / "session-1"
    archive = settings.state_root / "archive" / "session-1"
    active.mkdir(parents=True)
    archive.mkdir(parents=True)
    assert discover_runs(settings, include_archived=True, agent_run_id=None) == [
        ("session-1", "active", active)
    ]


def test_discovery_rejects_unsafe_archive_root(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    (settings.state_root / "runs").mkdir(parents=True)
    target = tmp_path / "outside"
    target.mkdir()
    os.symlink(target, settings.state_root / "archive")
    with pytest.raises(WorkflowError, match="archive root is unsafe"):
        discover_runs(settings, include_archived=True, agent_run_id=None)


def test_artifact_inventory_ignores_symlinks_locks_and_non_evidence(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    evidence = run / "status.json"
    evidence.write_text("{}", encoding="utf-8")
    (run / "notes.txt").write_text("not indexed", encoding="utf-8")
    (run / "index.lock").write_text("lock", encoding="utf-8")
    os.symlink(evidence, run / "linked.json")
    assert artifact_paths(run) == [evidence]


def test_stable_read_rejects_symlink_and_hashes_exact_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b'{"ok":true}\n')
    assert read_stable_bytes(source) == b'{"ok":true}\n'
    assert len(sha256_file(source)) == 64
    link = tmp_path / "linked.json"
    os.symlink(source, link)
    with pytest.raises(WorkflowError, match="cannot open indexed artifact"):
        read_stable_bytes(link)


def test_fingerprint_changes_when_source_mode_changes(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    artifact = run / "status.json"
    artifact.write_text('{"a":1}', encoding="utf-8")
    artifact.chmod(0o600)
    first = source_fingerprint(run)
    artifact.chmod(0o400)
    second = source_fingerprint(run)
    assert first != second
