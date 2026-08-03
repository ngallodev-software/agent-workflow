from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.repository_closeout import (
    create_repository_closeout,
    verify_repository_closeout,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path, *, branch: str = "main") -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True)
    _git(path, "config", "user.email", "tests@example.invalid")
    _git(path, "config", "user.name", "Tests")
    (path / "tracked.txt").write_text("initial\n", encoding="utf-8")
    _git(path, "add", "tracked.txt")
    _git(path, "commit", "-qm", "initial")
    return _git(path, "rev-parse", "HEAD")


def _commit(repo: Path, name: str, content: str) -> str:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", name)
    return _git(repo, "rev-parse", "HEAD")


def test_closeout_push_is_claimed_only_after_remote_revision_matches_head(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo = tmp_path / "repo"
    baseline = _init_repo(repo)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-qu", "origin", "main")
    head = _commit(repo, "second.txt", "second\n")

    receipt = create_repository_closeout(
        repo,
        output=tmp_path / "push-closeout.json",
        baseline_revision=baseline,
        fetch=True,
        push=True,
        integration_branch="main",
    )

    assert receipt["remote"]["revision_before"] == {
        "value": baseline,
        "verification": "verified",
    }
    assert receipt["comparison"] == {
        "ahead": 1,
        "behind": 0,
        "state": "ahead",
        "verification": "verified",
    }
    assert receipt["remote"]["push"]["result"] == "succeeded-verified"
    assert receipt["remote"]["revision_after"] == {
        "value": head,
        "verification": "verified",
    }
    assert receipt["integration"]["remote_revision"] == head
    assert receipt["integration"]["head_reachable"] is True
    assert receipt["claims"] == {"committed": True, "pushed": True, "merged": True}


def test_rejected_non_fast_forward_push_never_sets_pushed_claim(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    first = tmp_path / "first"
    _init_repo(first)
    _git(first, "remote", "add", "origin", str(remote))
    _git(first, "push", "-qu", "origin", "main")

    second = tmp_path / "second"
    subprocess.run(["git", "clone", "-q", "--branch", "main", str(remote), str(second)], check=True)
    _git(second, "config", "user.email", "tests@example.invalid")
    _git(second, "config", "user.name", "Tests")
    first_remote_head = _commit(first, "remote.txt", "remote movement\n")
    _git(first, "push", "-q", "origin", "main")
    local_head = _commit(second, "local.txt", "local movement\n")

    receipt = create_repository_closeout(second, output=tmp_path / "rejected.json", push=True)

    assert receipt["local"]["head"] == local_head
    assert receipt["remote"]["revision_before"] == {
        "value": first_remote_head,
        "verification": "verified",
    }
    assert receipt["remote"]["push"]["result"] == "failed"
    assert receipt["remote"]["push"]["returncode"] != 0
    assert receipt["remote"]["revision_after"] == {
        "value": first_remote_head,
        "verification": "verified",
    }
    assert receipt["claims"]["pushed"] is False


def test_remote_ahead_diverged_and_detached_states_are_distinct(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    seed = tmp_path / "seed"
    _init_repo(seed)
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-qu", "origin", "main")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--branch", "main", str(remote), str(clone)], check=True)
    _git(clone, "config", "user.email", "tests@example.invalid")
    _git(clone, "config", "user.name", "Tests")

    remote_head = _commit(seed, "remote.txt", "remote\n")
    _git(seed, "push", "-q", "origin", "main")
    behind = create_repository_closeout(clone, output=tmp_path / "remote-ahead.json", fetch=True)
    assert behind["remote"]["revision_before"]["value"] == remote_head
    assert behind["comparison"]["state"] == "behind"
    assert behind["comparison"]["verification"] == "verified"

    _commit(clone, "local.txt", "local\n")
    diverged = create_repository_closeout(clone, output=tmp_path / "diverged.json", fetch=True)
    assert diverged["comparison"]["state"] == "diverged"
    assert (diverged["comparison"]["ahead"], diverged["comparison"]["behind"]) == (1, 1)

    _git(clone, "checkout", "--detach", "-q")
    detached = create_repository_closeout(
        clone, output=tmp_path / "detached.json", push_branch="detached-review"
    )
    assert detached["local"]["detached"] is True
    assert detached["local"]["branch"] is None
    assert detached["remote"]["target_branch"] == "detached-review"
    with pytest.raises(WorkflowError, match="push requires a branch target"):
        create_repository_closeout(clone, output=tmp_path / "detached-push.json", push=True)


def test_closeout_security_matrix_rejects_ambiguous_paths_tampering_and_source_renames(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    invalid_classifications = (
        ({"operational_trees": ("state/",), "disposable_trees": ("state",)}, "both operational and disposable"),
        ({"operational_trees": ("../escape",)}, "safe relative path"),
        ({"operational_trees": ("state/",), "disposable_trees": ("state/cache/",)}, "both operational and disposable"),
    )
    for index, (kwargs, message) in enumerate(invalid_classifications):
        with pytest.raises(WorkflowError, match=message):
            create_repository_closeout(repo, output=tmp_path / f"invalid-{index}.json", **kwargs)

    receipt_path = tmp_path / "tampered.json"
    create_repository_closeout(repo, output=receipt_path)
    os.chmod(receipt_path, 0o644)
    receipt_path.write_text(
        receipt_path.read_text(encoding="utf-8").replace('"pushed": false', '"pushed": true'),
        encoding="utf-8",
    )
    with pytest.raises(WorkflowError, match="payload digest"):
        verify_repository_closeout(receipt_path)

    disposable = repo / ".codebase-memory"
    disposable.mkdir()
    _git(repo, "mv", "tracked.txt", ".codebase-memory/tracked.txt")
    renamed = create_repository_closeout(
        repo,
        output=tmp_path / "rename.json",
        disposable_trees=(".codebase-memory/",),
    )
    assert renamed["dirty_state"]["counts"]["source"] == 1
    assert renamed["claims"]["committed"] is False
