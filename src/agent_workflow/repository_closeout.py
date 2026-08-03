from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .contracts import validate_instance
from .errors import WorkflowError
from .process import EnvironmentPolicy, ProcessResult, require_command, run, run_bytes
from .util import expand_path, fsync_directory, utc_now

SCHEMA_ID = "agent-workflow/repository-closeout/v1"
_MAX_STATUS_BYTES = 4 * 1024 * 1024
_MAX_STATUS_ENTRIES = 20_000
_GIT_ENV = EnvironmentPolicy(unsafe_inherit=True, git_config_policy="operator")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_digest(value: dict[str, Any]) -> str:
    payload = {key: item for key, item in value.items() if key != "payload_sha256"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(encoded)


def _command_evidence(name: str, result: ProcessResult) -> dict[str, Any]:
    stdout = result.stdout.encode("utf-8", errors="surrogatepass") if isinstance(result.stdout, str) else result.stdout
    stderr = result.stderr.encode("utf-8", errors="surrogatepass") if isinstance(result.stderr, str) else result.stderr
    return {
        "name": name,
        "argv": list(result.argv),
        "returncode": result.returncode,
        "stdout_sha256": _sha256_bytes(stdout),
        "stdout_bytes": result.stdout_bytes,
        "stderr_sha256": _sha256_bytes(stderr),
        "stderr_bytes": result.stderr_bytes,
        "duration_seconds": result.duration_seconds,
        "error_category": result.error_category,
    }


def _git(repo: Path, *args: str, check: bool = False, timeout_seconds: float = 60) -> ProcessResult:
    return run(
        ["git", "-C", str(repo), *args],
        check=check,
        timeout_seconds=timeout_seconds,
        max_stdout_bytes=_MAX_STATUS_BYTES,
        max_stderr_bytes=512 * 1024,
        environment=_GIT_ENV,
    )


def _git_bytes(repo: Path, *args: str, check: bool = False) -> ProcessResult:
    return run_bytes(
        ["git", "-C", str(repo), *args],
        check=check,
        timeout_seconds=60,
        max_stdout_bytes=_MAX_STATUS_BYTES,
        max_stderr_bytes=512 * 1024,
        environment=_GIT_ENV,
    )


def _stdout(result: ProcessResult) -> str | None:
    value = str(result.stdout).strip()
    return value or None if result.returncode == 0 else None


def _normalize_tree(value: str) -> str:
    text = value.replace("\\", "/").strip("/")
    path = Path(text)
    if not text or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise WorkflowError(f"repository closeout tree must be a safe relative path: {value!r}")
    return text + "/"


def _tree_overlap(first: str, second: str) -> bool:
    return first == second or first.startswith(second) or second.startswith(first)


def _under(path: str, trees: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return any(normalized == tree.rstrip("/") or normalized.startswith(tree) for tree in trees)


def _classify(path: str, operational: tuple[str, ...], disposable: tuple[str, ...]) -> str:
    if _under(path, disposable):
        return "disposable"
    if _under(path, operational):
        return "operational"
    return "source"


def _classify_paths(
    paths: Iterable[str], operational: tuple[str, ...], disposable: tuple[str, ...]
) -> str:
    """Classify a rename/copy conservatively across every involved path."""
    values = {_classify(path, operational, disposable) for path in paths}
    if "source" in values:
        return "source"
    if "operational" in values:
        return "operational"
    return "disposable"


def _parse_porcelain(data: bytes, operational: tuple[str, ...], disposable: tuple[str, ...]) -> list[dict[str, Any]]:
    values = data.split(b"\0")
    entries: list[dict[str, Any]] = []
    index = 0
    while index < len(values):
        raw = values[index]
        index += 1
        if not raw:
            continue
        text = raw.decode("utf-8", errors="surrogateescape")
        if len(text) < 4 or text[2] != " ":
            raise WorkflowError("unexpected Git porcelain record in repository closeout")
        status_code = text[:2]
        path = text[3:]
        original_path = None
        if status_code[0] in {"R", "C"} or status_code[1] in {"R", "C"}:
            if index >= len(values) or not values[index]:
                raise WorkflowError("truncated Git rename/copy porcelain record")
            original_path = values[index].decode("utf-8", errors="surrogateescape")
            index += 1
        classification = _classify_paths(
            (path,) if original_path is None else (path, original_path),
            operational,
            disposable,
        )
        entries.append(
            {
                "status": status_code,
                "path": path,
                "original_path": original_path,
                "classification": classification,
            }
        )
        if len(entries) > _MAX_STATUS_ENTRIES:
            raise WorkflowError("repository closeout dirty-path count exceeds bounded limit")
    return entries


def _git_path(repo: Path, name: str) -> Path:
    result = _git(repo, "rev-parse", "--git-path", name)
    value = _stdout(result)
    if value is None:
        return repo / ".git" / name
    path = Path(value)
    return path if path.is_absolute() else (repo / path).resolve()


def _operation_state(repo: Path) -> list[str]:
    markers = {
        "merge": "MERGE_HEAD",
        "cherry-pick": "CHERRY_PICK_HEAD",
        "revert": "REVERT_HEAD",
        "bisect": "BISECT_LOG",
        "rebase-merge": "rebase-merge",
        "rebase-apply": "rebase-apply",
    }
    return sorted(label for label, marker in markers.items() if _git_path(repo, marker).exists())


def _tracking_details(repo: Path, branch: str | None) -> tuple[str | None, str | None, str | None]:
    if not branch:
        return None, None, None
    upstream_result = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    upstream = _stdout(upstream_result)
    remote = _stdout(_git(repo, "config", "--get", f"branch.{branch}.remote"))
    merge_ref = _stdout(_git(repo, "config", "--get", f"branch.{branch}.merge"))
    upstream_branch = merge_ref.removeprefix("refs/heads/") if merge_ref else None
    if remote == ".":
        remote = None
    return upstream, remote, upstream_branch


def _resolve_revision(repo: Path, ref: str | None) -> str | None:
    if not ref:
        return None
    result = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return _stdout(result)


def _ahead_behind(repo: Path, head: str, other: str | None) -> tuple[int | None, int | None, str]:
    if not other:
        return None, None, "no-upstream"
    result = _git(repo, "rev-list", "--left-right", "--count", f"{head}...{other}")
    if result.returncode != 0:
        return None, None, "unverified"
    try:
        ahead_text, behind_text = str(result.stdout).strip().split()
        ahead, behind = int(ahead_text), int(behind_text)
    except (ValueError, TypeError):
        return None, None, "unverified"
    if ahead == 0 and behind == 0:
        state = "equal"
    elif ahead and behind:
        state = "diverged"
    elif ahead:
        state = "ahead"
    else:
        state = "behind"
    return ahead, behind, state


def _ls_remote(repo: Path, remote: str, branch: str, commands: list[dict[str, Any]], name: str) -> tuple[str | None, str]:
    ref = f"refs/heads/{branch}"
    result = _git(repo, "ls-remote", "--exit-code", "--", remote, ref, timeout_seconds=90)
    commands.append(_command_evidence(name, result))
    if result.returncode != 0:
        return None, "failed"
    line = str(result.stdout).strip().splitlines()
    if len(line) != 1:
        return None, "failed"
    revision, _, returned_ref = line[0].partition("\t")
    if returned_ref != ref or len(revision) != 40 or any(char not in "0123456789abcdefABCDEF" for char in revision):
        return None, "failed"
    return revision.lower(), "verified"


def _ancestor(repo: Path, ancestor: str, descendant: str) -> bool | None:
    result = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _write_immutable_json(path: Path, value: dict[str, Any]) -> None:
    path = expand_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise WorkflowError(f"repository closeout receipt already exists: {path}")
    encoded = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fchmod(stream.fileno(), 0o444)
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise WorkflowError(f"repository closeout receipt already exists: {path}") from exc
        fsync_directory(path.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _comparison_verification(remote_state: str, network_mode: str) -> str:
    if remote_state == "verified":
        return "verified"
    if network_mode == "offline" and remote_state == "cached-unverified":
        return "cached-unverified"
    return "unverified"


def repository_closeout_semantic_errors(receipt: dict[str, Any]) -> list[str]:
    """Validate derived closeout claims independently of JSON shape."""
    errors: list[str] = []
    local = receipt.get("local", {})
    dirty = receipt.get("dirty_state", {})
    remote = receipt.get("remote", {})
    comparison = receipt.get("comparison", {})
    integration = receipt.get("integration", {})
    claims = receipt.get("claims", {})

    entries = dirty.get("entries", [])
    counts = dirty.get("counts", {})
    if isinstance(entries, list) and isinstance(counts, dict):
        observed = {
            key: sum(
                isinstance(item, dict) and item.get("classification") == key
                for item in entries
            )
            for key in ("source", "operational", "disposable")
        }
        if counts != observed:
            errors.append("dirty-state counts do not match classified entries")
        if dirty.get("entry_count") != len(entries):
            errors.append("dirty-state entry_count does not match entries")
        operations = local.get("operation_state") or []
        expected_commit_state = (
            "source-dirty"
            if observed["source"]
            else "source-clean-operational-dirty"
            if entries
            else "clean"
        )
        if local.get("commit_state") != expected_commit_state:
            errors.append("local commit_state does not match dirty-state classification")
        expected_committed = observed["source"] == 0 and not operations
        if local.get("source_changes_committed") is not expected_committed:
            errors.append("local source_changes_committed is inconsistent")
        if claims.get("committed") is not expected_committed:
            errors.append("committed claim is inconsistent with local repository state")

    fetch = remote.get("fetch", {})
    push = remote.get("push", {})
    network_mode = remote.get("network_mode")
    expected_mode = (
        "fetch-and-push"
        if fetch.get("attempted") and push.get("attempted")
        else "fetch"
        if fetch.get("attempted")
        else "push"
        if push.get("attempted")
        else "offline"
    )
    if network_mode != expected_mode:
        errors.append("remote network_mode does not match attempted operations")
    if not fetch.get("attempted") and fetch.get("result") != "not-attempted":
        errors.append("fetch result is inconsistent with attempted=false")
    if fetch.get("attempted") and fetch.get("result") == "not-attempted":
        errors.append("fetch result is inconsistent with attempted=true")
    if not push.get("attempted") and push.get("result") != "not-attempted":
        errors.append("push result is inconsistent with attempted=false")
    if push.get("attempted") and push.get("result") == "not-attempted":
        errors.append("push result is inconsistent with attempted=true")

    revision_after = remote.get("revision_after", {})
    verified_push = (
        push.get("result") == "succeeded-verified"
        and push.get("returncode") == 0
        and revision_after.get("verification") == "verified"
        and revision_after.get("value") == local.get("head")
    )
    if claims.get("pushed") is not verified_push:
        errors.append("pushed claim requires a verified post-push remote revision equal to local HEAD")
    if push.get("result") == "succeeded-verified" and not verified_push:
        errors.append("succeeded-verified push result is internally inconsistent")

    expected_merged = integration.get("merged_verified")
    if claims.get("merged") is not expected_merged:
        errors.append("merged claim does not match verified integration ancestry")

    ahead = comparison.get("ahead")
    behind = comparison.get("behind")
    state = comparison.get("state")
    if isinstance(ahead, int) and isinstance(behind, int):
        expected_state = (
            "equal"
            if ahead == 0 and behind == 0
            else "diverged"
            if ahead and behind
            else "ahead"
            if ahead
            else "behind"
        )
        if state not in {expected_state, "unverified"}:
            errors.append("comparison state does not match ahead/behind counts")
    if network_mode == "offline" and comparison.get("verification") == "verified":
        errors.append("offline comparison cannot be marked verified")
    return errors


def repository_closeout_summary(receipt: dict[str, Any]) -> dict[str, Any]:
    local = receipt["local"]
    dirty = receipt["dirty_state"]
    remote = receipt["remote"]
    comparison = receipt["comparison"]
    integration = receipt["integration"]
    return {
        "path": "repository-closeout.json",
        "payload_sha256": receipt["payload_sha256"],
        "baseline_revision": receipt.get("baseline_revision"),
        "local_head": local["head"],
        "local_branch": local["branch"],
        "commit_state": local["commit_state"],
        "dirty_counts": dirty["counts"],
        "remote_name": remote["name"],
        "remote_branch": remote["target_branch"],
        "remote_revision_before": remote["revision_before"]["value"],
        "remote_revision_after": remote["revision_after"]["value"],
        "remote_verification": remote["revision_after"]["verification"],
        "fetch_result": remote["fetch"]["result"],
        "push_result": remote["push"]["result"],
        "ahead": comparison["ahead"],
        "behind": comparison["behind"],
        "comparison_state": comparison["state"],
        "comparison_verification": comparison["verification"],
        "integration_branch": integration["branch"],
        "integration_revision": integration["remote_revision"],
        "merged_verified": integration["merged_verified"],
        "claims": receipt["claims"],
    }


def create_repository_closeout(
    repo: Path,
    *,
    output: Path,
    baseline_revision: str | None = None,
    remote: str = "origin",
    fetch: bool = False,
    push: bool = False,
    push_branch: str | None = None,
    set_upstream: bool = False,
    integration_branch: str | None = None,
    operational_trees: Iterable[str] = (),
    disposable_trees: Iterable[str] = (),
) -> dict[str, Any]:
    require_command("git")
    repo = expand_path(repo)
    root_result = _git(repo, "rev-parse", "--show-toplevel", check=True)
    root = Path(str(root_result.stdout).strip()).resolve()
    commands: list[dict[str, Any]] = [_command_evidence("repository-root", root_result)]

    head_result = _git(root, "rev-parse", "--verify", "HEAD", check=True)
    commands.append(_command_evidence("local-head", head_result))
    head = str(head_result.stdout).strip()
    branch_result = _git(root, "branch", "--show-current")
    commands.append(_command_evidence("local-branch", branch_result))
    branch = _stdout(branch_result)
    detached = branch is None

    common_dir_result = _git(root, "rev-parse", "--git-common-dir", check=True)
    commands.append(_command_evidence("git-common-dir", common_dir_result))
    common_dir_text = str(common_dir_result.stdout).strip()
    common_dir = Path(common_dir_text)
    if not common_dir.is_absolute():
        common_dir = (root / common_dir).resolve()
    identity_material = f"{root}\0{common_dir}".encode("utf-8", errors="surrogatepass")

    operational = tuple(sorted({_normalize_tree(item) for item in operational_trees}))
    disposable = tuple(sorted({_normalize_tree(item) for item in disposable_trees}))
    overlap = sorted(
        first
        for first in operational
        for second in disposable
        if _tree_overlap(first, second)
    )
    if overlap:
        raise WorkflowError(f"repository closeout tree cannot be both operational and disposable: {overlap[0]}")

    status_result = _git_bytes(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    commands.append(_command_evidence("porcelain-status", status_result))
    if status_result.returncode != 0 or status_result.stdout_truncated:
        raise WorkflowError("cannot collect bounded Git porcelain status for repository closeout")
    status_bytes = bytes(status_result.stdout)
    dirty_entries = _parse_porcelain(status_bytes, operational, disposable)
    counts = {key: sum(item["classification"] == key for item in dirty_entries) for key in ("source", "operational", "disposable")}
    operations = _operation_state(root)
    commit_state = "source-dirty" if counts["source"] else "source-clean-operational-dirty" if dirty_entries else "clean"

    resolved_baseline = None
    if baseline_revision is not None:
        resolved_baseline = _resolve_revision(root, baseline_revision)
        if resolved_baseline is None:
            raise WorkflowError(f"baseline revision is not a readable commit: {baseline_revision}")

    upstream_ref, configured_remote, upstream_branch = _tracking_details(root, branch)
    remote_name = configured_remote or remote
    if not remote_name or remote_name.startswith("-"):
        raise WorkflowError(f"invalid Git remote name: {remote_name!r}")
    target_branch = push_branch or upstream_branch or branch
    if push_branch:
        check_ref = _git(root, "check-ref-format", "--branch", push_branch)
        commands.append(_command_evidence("validate-push-branch", check_ref))
        if check_ref.returncode != 0:
            raise WorkflowError(f"invalid push branch: {push_branch}")
    if integration_branch:
        check_ref = _git(root, "check-ref-format", "--branch", integration_branch)
        commands.append(_command_evidence("validate-integration-branch", check_ref))
        if check_ref.returncode != 0:
            raise WorkflowError(f"invalid integration branch: {integration_branch}")

    network_mode = "fetch-and-push" if fetch and push else "fetch" if fetch else "push" if push else "offline"
    fetch_result = "not-attempted"
    fetch_at = None
    if fetch:
        fetch_command = _git(root, "fetch", "--prune", "--no-tags", "--", remote_name, timeout_seconds=120)
        commands.append(_command_evidence("fetch-remote", fetch_command))
        fetch_at = utc_now()
        fetch_result = "succeeded" if fetch_command.returncode == 0 else "failed"

    cached_tracking_ref = upstream_ref
    if cached_tracking_ref is None and target_branch:
        cached_tracking_ref = f"refs/remotes/{remote_name}/{target_branch}"
    cached_remote_revision = _resolve_revision(root, cached_tracking_ref)

    remote_revision_before = None
    remote_before_state = "unverified"
    if (fetch or push) and target_branch:
        remote_revision_before, remote_before_state = _ls_remote(root, remote_name, target_branch, commands, "remote-before")
    elif cached_remote_revision:
        remote_revision_before = cached_remote_revision
        remote_before_state = "cached-unverified"

    comparison_revision = cached_remote_revision if fetch_result == "succeeded" else remote_revision_before
    ahead, behind, comparison_state = _ahead_behind(root, head, comparison_revision)
    if remote_before_state not in {"verified", "cached-unverified"} and comparison_state != "no-upstream":
        comparison_state = "unverified"

    push_attempted = push
    push_returncode = None
    push_result = "not-attempted"
    push_target_ref = f"refs/heads/{target_branch}" if target_branch else None
    if push:
        if not target_branch:
            raise WorkflowError("push requires a branch target; use --push-branch for a detached HEAD")
        argv = ["push"]
        if set_upstream:
            argv.append("--set-upstream")
        argv.extend(["--", remote_name, f"HEAD:{push_target_ref}"])
        push_command = _git(root, *argv, timeout_seconds=120)
        commands.append(_command_evidence("push", push_command))
        push_returncode = push_command.returncode
        push_result = "succeeded-unverified" if push_command.returncode == 0 else "failed"

    remote_revision_after = remote_revision_before
    remote_after_state = remote_before_state
    if push and target_branch:
        remote_revision_after, remote_after_state = _ls_remote(root, remote_name, target_branch, commands, "remote-after")
        if push_returncode == 0 and remote_after_state == "verified" and remote_revision_after == head:
            push_result = "succeeded-verified"

    integration_revision = None
    integration_state = "not-requested"
    head_reachable = None
    merged_verified = None
    if integration_branch:
        if fetch or push:
            integration_revision, integration_state = _ls_remote(root, remote_name, integration_branch, commands, "integration-remote")
        else:
            integration_revision = _resolve_revision(root, f"refs/remotes/{remote_name}/{integration_branch}")
            integration_state = "cached-unverified" if integration_revision else "unverified"
        if integration_revision and _resolve_revision(root, integration_revision):
            head_reachable = _ancestor(root, head, integration_revision)
        if integration_state == "verified" and head_reachable is not None:
            merged_verified = head_reachable

    receipt: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "captured_at": utc_now(),
        "repository": {
            "root": str(root),
            "identity_sha256": _sha256_bytes(identity_material),
            "git_common_dir_sha256": _sha256_bytes(str(common_dir).encode("utf-8", errors="surrogatepass")),
        },
        "baseline_revision": resolved_baseline,
        "local": {
            "head": head,
            "branch": branch,
            "detached": detached,
            "upstream_ref": upstream_ref,
            "upstream_remote": configured_remote,
            "upstream_branch": upstream_branch,
            "operation_state": operations,
            "commit_state": commit_state,
            "source_changes_committed": counts["source"] == 0 and not operations,
        },
        "dirty_state": {
            "porcelain_sha256": _sha256_bytes(status_bytes),
            "entry_count": len(dirty_entries),
            "counts": counts,
            "operational_trees": list(operational),
            "disposable_trees": list(disposable),
            "entries": dirty_entries,
        },
        "remote": {
            "name": remote_name,
            "network_mode": network_mode,
            "target_branch": target_branch,
            "tracking_ref": cached_tracking_ref,
            "fetch": {
                "attempted": fetch,
                "result": fetch_result,
                "completed_at": fetch_at,
            },
            "revision_before": {
                "value": remote_revision_before,
                "verification": remote_before_state,
            },
            "push": {
                "attempted": push_attempted,
                "result": push_result,
                "returncode": push_returncode,
                "target_ref": push_target_ref,
                "set_upstream": set_upstream,
            },
            "revision_after": {
                "value": remote_revision_after,
                "verification": remote_after_state,
            },
        },
        "comparison": {
            "ahead": ahead,
            "behind": behind,
            "state": comparison_state,
            "verification": _comparison_verification(remote_before_state, network_mode),
        },
        "integration": {
            "branch": integration_branch,
            "remote_revision": integration_revision,
            "verification": integration_state,
            "head_reachable": head_reachable,
            "merged_verified": merged_verified,
        },
        "commands": commands,
        "claims": {
            "committed": counts["source"] == 0 and not operations,
            "pushed": push_result == "succeeded-verified",
            "merged": merged_verified,
        },
    }
    semantic_errors = repository_closeout_semantic_errors(receipt)
    if semantic_errors:
        raise WorkflowError("invalid repository closeout: " + "; ".join(semantic_errors))
    receipt["payload_sha256"] = _canonical_digest(receipt)
    validate_instance(receipt, SCHEMA_ID, artifact="repository closeout receipt")
    _write_immutable_json(output, receipt)
    return receipt


def validate_repository_closeout_payload(data: bytes, *, artifact: str = "repository closeout receipt") -> dict[str, Any]:
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid {artifact}: {exc}") from exc
    if not isinstance(receipt, dict):
        raise WorkflowError(f"invalid {artifact}: expected JSON object")
    validate_instance(receipt, SCHEMA_ID, artifact=artifact)
    expected = _canonical_digest(receipt)
    if receipt.get("payload_sha256") != expected:
        raise WorkflowError("repository closeout receipt payload digest does not match")
    semantic_errors = repository_closeout_semantic_errors(receipt)
    if semantic_errors:
        raise WorkflowError("invalid repository closeout receipt: " + "; ".join(semantic_errors))
    return receipt


def verify_repository_closeout(path: Path) -> dict[str, Any]:
    path = expand_path(path)
    read = path.read_bytes()
    receipt = validate_repository_closeout_payload(read, artifact=str(path))
    expected = str(receipt["payload_sha256"])
    try:
        mode = stat.S_IMODE(path.lstat().st_mode)
    except OSError as exc:
        raise WorkflowError(f"cannot inspect repository closeout receipt: {path}") from exc
    return {
        "schema": "agent-workflow/repository-closeout-verification/v1",
        "path": str(path),
        "payload_sha256": expected,
        "schema_valid": True,
        "digest_valid": True,
        "read_only_mode": mode & 0o222 == 0,
        "mode": mode,
        "claims": receipt.get("claims"),
        "local_head": receipt.get("local", {}).get("head"),
        "remote_revision_after": receipt.get("remote", {}).get("revision_after", {}).get("value"),
    }
