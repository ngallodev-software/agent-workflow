from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..errors import WorkflowError
from ..path import inventory_tree
from ..process import run, run_bytes
from ..util import atomic_write_json, utc_now


CODEBASE_MEMORY_TREE = ".codebase-memory"
CODEBASE_MEMORY_MAX_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class ScopePolicy:
    authorized_root: Path
    writable_paths: tuple[str, ...] = ()
    writable_trees: tuple[str, ...] = ()
    disposable_trees: tuple[str, ...] = ()


def _nul_values(data: bytes) -> list[str]:
    return [item.decode("utf-8", errors="surrogateescape") for item in data.split(b"\0") if item]


def _git_roots(root: Path) -> list[Path]:
    roots: set[Path] = set()
    if (root / ".git").exists():
        roots.add(root)
    for directory, names, files in os.walk(root, followlinks=False):
        here = Path(directory)
        if ".git" in names or ".git" in files:
            roots.add(here.resolve())
            if ".git" in names:
                names.remove(".git")
    return sorted(roots, key=lambda item: item.as_posix())


def _git_facts(
    repo: Path, root: Path, baseline_head: str | None = None
) -> dict[str, Any]:
    def git(*args: str, check: bool = True) -> bytes:
        result = run_bytes(
            ["git", "-C", str(repo), *args],
            check=check,
            timeout_seconds=60,
            max_stdout_bytes=4 * 1024 * 1024,
            max_stderr_bytes=256 * 1024,
        )
        if result.stdout_truncated:
            raise WorkflowError(f"git scope output exceeded capture limit: {args[0] if args else 'command'}")
        return result.stdout

    head = git("rev-parse", "HEAD", check=False).decode().strip() or None
    branch = git("branch", "--show-current", check=False).decode().strip() or "(detached)"
    return {
        "root": repo.relative_to(root).as_posix() or ".",
        "head": head,
        "branch": branch,
        "committed": _nul_values(
            git(
                "diff",
                "--name-status",
                "-z",
                "--find-renames",
                "--find-copies",
                f"{baseline_head}..HEAD" if baseline_head else "HEAD..HEAD",
                check=False,
            )
        ),
        "staged": _nul_values(git("diff", "--cached", "--name-status", "-z", "--find-renames", "--find-copies", check=False)),
        "unstaged": _nul_values(git("diff", "--name-status", "-z", "--find-renames", "--find-copies", check=False)),
        "untracked": _nul_values(git("ls-files", "--others", "--exclude-standard", "-z", check=False)),
        "ignored": _nul_values(git("ls-files", "--others", "--ignored", "--exclude-standard", "-z", check=False)),
        "submodules": run(
            ["git", "-C", str(repo), "submodule", "status", "--recursive"],
            check=False,
            timeout_seconds=60,
            max_stdout_bytes=256 * 1024,
            max_stderr_bytes=64 * 1024,
        ).stdout.splitlines(),
    }


def _under_tree(relative: str, trees: tuple[str, ...]) -> bool:
    normalized = relative.rstrip("/")
    return any(normalized == tree.rstrip("/") or normalized.startswith(tree.rstrip("/") + "/") for tree in trees)


def _tooling_artifact(root: Path, relative: str, disposable: tuple[str, ...]) -> dict[str, Any] | None:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return None
    authorized = _under_tree(relative, disposable)
    cleanup_policy = "host-owned-disposable" if authorized else "not-authorized"
    try:
        root_info = path.lstat()
        if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
            raise WorkflowError(f"tooling artifact tree is unsafe: {relative}")
        entries = inventory_tree(path)
        digest = hashlib.sha256()
        size_bytes = 0
        file_count = 0
        for entry in entries:
            digest.update(entry.path.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")
            digest.update(entry.kind.encode("ascii"))
            digest.update(b"\0")
            digest.update(str(entry.mode).encode("ascii"))
            digest.update(b"\0")
            digest.update(str(entry.size).encode("ascii"))
            digest.update(b"\0")
            digest.update((entry.sha256 or "").encode("ascii"))
            digest.update(b"\n")
            if entry.kind == "file":
                size_bytes += entry.size
                file_count += 1
        return {
            "path": relative + "/",
            "tool": "codebase-memory",
            "valid": True,
            "owner_uid": root_info.st_uid,
            "owner_gid": root_info.st_gid,
            "mode": stat.S_IMODE(root_info.st_mode),
            "file_count": file_count,
            "size_bytes": size_bytes,
            "tree_sha256": digest.hexdigest(),
            "authorized_disposable": authorized,
            "cleanup_policy": cleanup_policy,
            "size_limit_bytes": CODEBASE_MEMORY_MAX_BYTES,
            "within_size_limit": size_bytes <= CODEBASE_MEMORY_MAX_BYTES,
            "error": None,
        }
    except (OSError, WorkflowError) as exc:
        try:
            info = path.lstat()
            owner_uid, owner_gid, mode = info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)
        except OSError:
            owner_uid = owner_gid = mode = None
        return {
            "path": relative + "/",
            "tool": "codebase-memory",
            "valid": False,
            "owner_uid": owner_uid,
            "owner_gid": owner_gid,
            "mode": mode,
            "file_count": 0,
            "size_bytes": 0,
            "tree_sha256": None,
            "authorized_disposable": authorized,
            "cleanup_policy": cleanup_policy,
            "size_limit_bytes": CODEBASE_MEMORY_MAX_BYTES,
            "within_size_limit": False,
            "error": str(exc),
        }


def _inventory(root: Path, disposable: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    excluded: list[str] = []
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(directory)
        relative_dir = here.relative_to(root).as_posix()
        kept: list[str] = []
        for name in sorted(names):
            relative = (Path(relative_dir) / name).as_posix() if relative_dir != "." else name
            if name == ".git" or _under_tree(relative, disposable):
                excluded.append(relative + "/")
            else:
                kept.append(name)
        names[:] = kept
        for name in sorted(files):
            path = here / name
            relative = path.relative_to(root).as_posix()
            if _under_tree(relative, disposable):
                excluded.append(relative)
                continue
            info = path.lstat()
            item: dict[str, Any] = {
                "path": relative,
                "mode": stat.S_IMODE(info.st_mode),
                "size": info.st_size,
            }
            if stat.S_ISLNK(info.st_mode):
                resolved = path.resolve(strict=False)
                try:
                    resolved.relative_to(root)
                    escapes_root = False
                except ValueError:
                    escapes_root = True
                item.update(
                    kind="symlink",
                    target=os.readlink(path),
                    escapes_root=escapes_root,
                )
            elif stat.S_ISREG(info.st_mode):
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                item.update(kind="file", sha256=digest.hexdigest())
            else:
                item.update(kind="other")
            items.append(item)
    return items, sorted(excluded)


def collect_scope(
    root: Path,
    *,
    phase: Literal["baseline", "post"],
    policy: ScopePolicy,
    receipt_dir: Path,
) -> dict[str, Any]:
    root = root.resolve()
    authorized = policy.authorized_root.resolve()
    try:
        root.relative_to(authorized)
    except ValueError as exc:
        raise WorkflowError(f"scope root escapes authorized root: {root}") from exc
    receipt_dir.mkdir(parents=True, exist_ok=True)
    inventory, excluded = _inventory(root, policy.disposable_trees)
    tooling_artifacts = [
        item
        for item in (_tooling_artifact(root, CODEBASE_MEMORY_TREE, policy.disposable_trees),)
        if item is not None
    ]
    baseline_heads: dict[str, str] = {}
    baseline_path = receipt_dir / "scope-baseline.json"
    if phase == "post" and baseline_path.is_file():
        try:
            prior = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_heads = {
                str(item["root"]): str(item["head"])
                for item in prior.get("repositories", [])
                if isinstance(item, dict) and item.get("head")
            }
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise WorkflowError(f"cannot read scope baseline: {exc}") from exc
    repositories = []
    for repo in _git_roots(root):
        relative = repo.relative_to(root).as_posix() or "."
        repositories.append(_git_facts(repo, root, baseline_heads.get(relative)))
    result = {
        "schema": "agent-workflow/scope-snapshot/v1",
        "phase": phase,
        "root": str(root),
        "captured_at": utc_now(),
        "policy": {
            "authorized_root": str(authorized),
            "writable_paths": list(policy.writable_paths),
            "writable_trees": list(policy.writable_trees),
            "disposable_trees": list(policy.disposable_trees),
        },
        "repositories": repositories,
        "inventory": inventory,
        "excluded": excluded,
        "tooling_artifacts": tooling_artifacts,
    }
    atomic_write_json(receipt_dir / f"scope-{phase}.json", result)
    return result


def compare_scope(
    baseline: dict[str, Any], post: dict[str, Any], policy: ScopePolicy
) -> dict[str, Any]:
    before = {item["path"]: item for item in baseline.get("inventory", [])}
    after = {item["path"]: item for item in post.get("inventory", [])}
    paths = sorted(set(before) | set(after))
    changes: list[dict[str, str]] = []
    violations: list[str] = []
    for item in post.get("inventory", []):
        if isinstance(item, dict) and item.get("escapes_root") is True:
            violations.append(str(item.get("path")))
    for path in paths:
        if before.get(path) == after.get(path):
            continue
        kind = "introduced" if path not in before else "removed" if path not in after else "modified"
        changes.append({"path": path, "change": kind})
        allowed = (
            path in policy.writable_paths
            or _under_tree(path, policy.writable_trees)
            or _under_tree(path, policy.disposable_trees)
        )
        if not allowed:
            violations.append(path)
    for artifact in post.get("tooling_artifacts", []):
        if not isinstance(artifact, dict):
            continue
        if (
            artifact.get("valid") is not True
            or artifact.get("authorized_disposable") is not True
            or artifact.get("within_size_limit") is not True
        ):
            violations.append(str(artifact.get("path") or CODEBASE_MEMORY_TREE))
    before_repos = {item["root"] for item in baseline.get("repositories", [])}
    after_repos = {item["root"] for item in post.get("repositories", [])}
    repository_changes = sorted(before_repos ^ after_repos)
    violations.extend(f"{path}/.git" for path in repository_changes if path != ".")
    return {
        "changes": changes,
        "repository_changes": repository_changes,
        "violations": sorted(set(violations)),
    }
