from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..errors import WorkflowError
from ..process import run, run_bytes
from ..util import atomic_write_json, utc_now


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
        return run_bytes(["git", "-C", str(repo), *args], check=check).stdout

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
        "submodules": run(["git", "-C", str(repo), "submodule", "status", "--recursive"], check=False).stdout.splitlines(),
    }


def _under_tree(relative: str, trees: tuple[str, ...]) -> bool:
    normalized = relative.rstrip("/")
    return any(normalized == tree.rstrip("/") or normalized.startswith(tree.rstrip("/") + "/") for tree in trees)


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
        allowed = path in policy.writable_paths or _under_tree(path, policy.writable_trees)
        if not allowed:
            violations.append(path)
    before_repos = {item["root"] for item in baseline.get("repositories", [])}
    after_repos = {item["root"] for item in post.get("repositories", [])}
    repository_changes = sorted(before_repos ^ after_repos)
    violations.extend(f"{path}/.git" for path in repository_changes if path != ".")
    return {
        "changes": changes,
        "repository_changes": repository_changes,
        "violations": sorted(set(violations)),
    }
