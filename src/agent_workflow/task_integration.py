"""Host-owned integration of independently accepted OpenSpec task runs."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .config import Settings
from .contracts import validate_instance
from .errors import WorkflowError
from .eval.scope import ScopePolicy, compare_scope
from .lifecycle import lifecycle_receipts
from .process import EnvironmentPolicy, run, run_bytes
from .receipts import read_sealed_artifact_bytes, read_sealed_contract, read_sealed_json, verify_seal_details
from .state import run_dir
from .worktrees import list_worktrees
from .path import read_regular_file
from .repository_closeout import _write_immutable_json
from .git import common_administrative_dir
from .util import utc_now

SCHEMA = "agent-workflow/task-integration/v1"
_COMMIT_ENV = {"GIT_COMMITTER_NAME": "Agent-Workflow Integration",
               "GIT_COMMITTER_EMAIL": "agent-workflow@localhost",
               "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00"}



def _git(repo: Path, *args: str, check: bool = True, env: dict[str, str] | None = None,
         binary: bool = False):
    # The repository can contain worker-controlled hooks and diff drivers.
    execute = run_bytes if binary else run
    options = ["-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
               "-c", "diff.renames=false", "-c", "core.fsmonitor=false"]
    if any(item in args for item in ("checkout", "cherry-pick", "worktree")):
        configured = run(("git", "config", "--null", "--name-only", "--get-regexp",
                          r"^(merge\..*\.driver|filter\..*\.(clean|smudge|process|required))$"),
                         cwd=repo, check=False)
        for key in str(configured.stdout).strip("\x00").split("\x00"):
            if key:
                value = "/bin/false" if key.startswith("merge.") else ("false" if key.endswith(".required") else "")
                options.extend(["-c", f"{key}={value}"])
    result = execute(("git", *options, *args), cwd=repo, check=check,
                     environment=EnvironmentPolicy(values=env or {}),
                     timeout_seconds=120, max_stdout_bytes=16 * 1024 * 1024)
    if result.stdout_truncated or result.stderr_truncated:
        raise WorkflowError("integration Git evidence exceeded capture limit")
    return result


def _idle(repo: Path) -> None:
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
                   "rebase-merge", "rebase-apply", "sequencer"):
        path = Path(_git(repo, "rev-parse", "--git-path", marker).stdout.strip())
        if (path if path.is_absolute() else repo / path).exists():
            raise WorkflowError("repository has an unfinished Git operation")


def _sha(path: Path) -> str:
    return read_regular_file(path).sha256


def _json(path: Path) -> Any:
    try:
        return json.loads(read_regular_file(path).data.decode("utf-8"))
    except (ValueError, OSError) as exc:
        raise WorkflowError(f"invalid integration JSON: {path}") from exc


def _git_root(path: Path) -> Path:
    result = run(("git", "rev-parse", "--show-toplevel"), cwd=path, timeout_seconds=30)
    return Path(str(result.stdout).strip()).resolve()


def _clean(path: Path) -> bool:
    return not _git(path, "status", "--porcelain", "--untracked-files=all").stdout.strip()


def _commit(repo: Path, revision: str) -> dict[str, str]:
    result = _git(repo, "show", "-s", "--format=%H%x00%P%x00%T%x00%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%B", revision)
    values = str(result.stdout).split("\x00", 9)
    if len(values) != 10:
        raise WorkflowError(f"cannot read commit metadata: {revision}")
    return dict(zip(("commit", "parents", "tree", "author", "author_email", "authored_at", "committer", "committer_email", "committed_at", "message"), values))


def _relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (bool(value) and not path.is_absolute() and ".." not in path.parts
            and "\\" not in value and "\x00" not in value)


def _safe_path(value: str) -> bool:
    return _relative_path(value) and "openspec" not in PurePosixPath(value).parts



def _validate_command_file(path: Path) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise WorkflowError("commands file must be a regular file")
    commands = _json(path)
    if not isinstance(commands, list) or not commands:
        raise WorkflowError("commands file must be a non-empty JSON array")
    seen: set[str] = set()
    for item in commands:
        if not isinstance(item, dict) or set(item) != {"id", "argv", "cwd", "timeout_seconds"}:
            raise WorkflowError("each command must contain exactly id, argv, cwd, timeout_seconds")
        if not isinstance(item["id"], str) or not item["id"] or item["id"] in seen:
            raise WorkflowError("command IDs must be unique non-empty strings")
        seen.add(item["id"])
        if not isinstance(item["argv"], list) or not item["argv"] or any(not isinstance(x, str) or "\x00" in x for x in item["argv"]):
            raise WorkflowError("command argv must be a non-empty string array")
        if not isinstance(item["cwd"], str) or not _safe_path(item["cwd"] or "."):
            raise WorkflowError("command cwd must be a safe repository-relative path")
        if not isinstance(item["timeout_seconds"], int) or isinstance(item["timeout_seconds"], bool) or item["timeout_seconds"] < 1:
            raise WorkflowError("command timeout_seconds must be a positive integer")
    return commands


def _accepted_run(settings: Settings, repo: Path, run_id: str) -> dict[str, Any]:
    directory = run_dir(settings, run_id)
    final, seal_hash = verify_seal_details(directory)
    binding, binding_hash = read_sealed_contract(directory, final, "job-binding.json", "agent-workflow/job-binding/v2")
    completion, completion_hash = read_sealed_contract(directory, final, "completion.json", "agent-workflow/completion/v1")
    status, _ = read_sealed_contract(directory, final, "final-status.json", "agent-workflow/agent-run-status/v1")
    collection, _ = read_sealed_contract(directory, final, "collections/completion.json", "agent-workflow/completion-collection/v1")
    source = binding["source_specification"]
    source_receipt, source_hash = read_sealed_contract(directory, final, "jobs/source-specification.json", "agent-workflow/source-specification-import/v1")
    job, job_hash = read_sealed_contract(directory, final, "jobs/native-job.json", "agent-workflow/native-job/v2")
    if (source_hash != source["stored_sha256"] or source_hash != source["source_sha256"]
            or job_hash != binding["job_stored_sha256"] or job_hash != binding["job_source_sha256"]
            or job["source_specification"]["sha256"] != source_hash
            or job["source_specification"]["task_refs"] != source["task_refs"]
            or job["scope"] != binding["scope"]):
        raise WorkflowError(f"sealed job/source binding hashes or scope disagree: {run_id}")
    if len(source["task_refs"]) != 1:
        raise WorkflowError(f"run must bind exactly one imported task: {run_id}")
    task_id = source["task_refs"][0]
    if (any(value != run_id for value in (final["agent_run_id"], binding["agent_run_id"],
                                         completion["agent_run_id"], status["agent_run_id"]))
            or any(value != task_id for value in (binding["job_id"], binding["ticket_id"],
                                                  job["job_id"], job["ticket_id"], completion["ticket_id"]))):
        raise WorkflowError(f"sealed task, ticket, job, or run identities do not match: {run_id}")
    tasks = [task for task in source_receipt["task_map"] if task["agent_workflow_task_id"] == task_id]
    if len(tasks) != 1 or tasks[0]["done_at_import"] is not False:
        raise WorkflowError(f"task is not pending in its frozen OpenSpec import: {run_id}")
    if (completion["result"] != "completed" or status["status"] != "completed"
            or collection["validation_status"] != "valid"):
        raise WorkflowError(f"sealed execution is not valid and completed: {run_id}")
    receipts = lifecycle_receipts(directory, expected_final_receipt_sha256=seal_hash)
    if (len(receipts) < 2 or receipts[-1]["receipt"]["action"] != "accepted"
            or receipts[-2]["receipt"]["action"] != "reviewed"
            or receipts[-1]["receipt"]["revision"] != completion["head_revision"]):
        raise WorkflowError(f"run is not host-accepted at its sealed revision: {run_id}")
    baseline = str(completion.get("base_revision") or "")
    if source_receipt.get("repository", {}).get("revision") != baseline:
        raise WorkflowError(f"run baseline differs from frozen source import: {run_id}")
    head = str(completion.get("head_revision") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", baseline) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise WorkflowError(f"run has invalid source/head revision: {run_id}")
    if not _git(repo, "cat-file", "-e", f"{head}^{{commit}}", check=False).ok:
        raise WorkflowError(f"task commit is unavailable in repository: {head}")
    commit = _commit(repo, head)
    if commit["parents"] != baseline:
        raise WorkflowError(f"task must contain exactly one non-merge commit from source baseline: {run_id}")
    original_worktree = Path(binding.get("worktree", "")).resolve()
    if not original_worktree.is_dir():
        raise WorkflowError(f"input task worktree is unavailable: {run_id}")
    _idle(original_worktree)
    if _git(original_worktree, "rev-parse", "HEAD").stdout.strip() != head or not _clean(original_worktree):
        raise WorkflowError(f"input task worktree must remain at its sealed clean head: {run_id}")
    if common_administrative_dir(original_worktree) != common_administrative_dir(repo):
        raise WorkflowError(f"input task worktree does not share repository identity: {run_id}")
    baseline_evidence, _ = read_sealed_json(directory, final, "source-baseline.json")
    primary = baseline_evidence.get("components", {}).get("primary", {})
    if primary.get("head") != baseline or Path(primary.get("path", "")).resolve() != original_worktree:
        raise WorkflowError(f"sealed source baseline disagrees with binding: {run_id}")
    changed = _git(repo, "diff", "--no-renames", "--name-only", "-z", baseline, head, binary=True).stdout.decode("utf-8").strip("\x00").split("\x00")
    for revision in (baseline, head):
        modes = _git(repo, "ls-tree", "-r", "-z", revision, "--", *changed, binary=True).stdout.split(b"\x00")
        if any(entry and entry.split(b" ", 1)[0] not in {b"100644", b"100755"} for entry in modes):
            raise WorkflowError("integration only supports regular source files, not symlinks/submodules")
    scope = binding.get("scope", {})
    allowed = set(scope.get("writable_paths", [])) | set(scope.get("writable_trees", []))
    if sorted(completion.get("changed_files", [])) != sorted(changed):
        raise WorkflowError(f"sealed completion changed-file list disagrees with commit: {run_id}")
    if not changed or any(not _safe_path(item) or not any(item == p or (p in scope.get("writable_trees", []) and item.startswith(p.rstrip("/") + "/")) for p in allowed) for item in changed):
        raise WorkflowError(f"task commit changes paths outside sealed writable scope: {run_id}")
    for artifact in source_receipt.get("artifacts", []):
        path = artifact.get("path")
        if not isinstance(path, str) or not _relative_path(path):
            raise WorkflowError("unsafe frozen planning path")
        for revision in (baseline, head):
            blob = _git(repo, "show", f"{revision}:{path}", binary=True).stdout
            if hashlib.sha256(blob).hexdigest() != artifact.get("sha256"):
                raise WorkflowError(f"frozen OpenSpec planning bytes changed: {path}")
    _validate_diff_evidence(repo, directory, final, binding, completion)
    return {"run_id": run_id, "run_dir": directory, "seal_sha256": seal_hash,
            "binding_sha256": binding_hash, "completion_sha256": completion_hash,
            "binding": binding, "completion": completion, "baseline": baseline,
            "head": head, "commit": commit, "changed_paths": sorted(changed),
            "task_id": source["task_refs"][0], "source": source, "scope": scope}


def _validate_diff_evidence(repo, directory, final, binding, completion):
    """Bind Git object bytes to the already sealed source-scope inventories."""
    baseline, head = completion["base_revision"], completion["head_revision"]
    before, _ = read_sealed_contract(directory, final, "scope/scope-baseline.json", "agent-workflow/scope-snapshot/v1")
    after, _ = read_sealed_contract(directory, final, "scope/scope-post.json", "agent-workflow/scope-snapshot/v1")
    policy = ScopePolicy(authorized_root=Path(binding["worktree"]), **{
        key: tuple(value) for key, value in binding["scope"].items()})
    if compare_scope(before, after, policy)["violations"]:
        raise WorkflowError("sealed source changes violate writable scope")
    for revision, snapshot in ((baseline, before), (head, after)):
        repositories = [row for row in snapshot["repositories"] if row["root"] == "."]
        if len(repositories) != 1 or repositories[0]["head"] != revision:
            raise WorkflowError("sealed scope source revision disagrees with task commit")
        inventory = {row["path"]: row for row in snapshot["inventory"]}
        for path in completion["changed_files"]:
            blob = _git(repo, "show", f"{revision}:{path}", binary=True, check=False)
            entry = inventory.get(path)
            if blob.ok:
                if (not entry or entry["kind"] != "file" or entry["size"] != len(blob.stdout)
                        or entry["sha256"] != hashlib.sha256(blob.stdout).hexdigest()):
                    raise WorkflowError("sealed source inventory does not match Git commit bytes")
            elif entry is not None:
                raise WorkflowError("sealed source inventory contains an absent Git path")
    patch, _ = read_sealed_artifact_bytes(directory, final, "patch.diff")
    actual = _git(repo, "diff", "--no-ext-diff", "--no-textconv", "--binary", "--full-index",
                  baseline, head, binary=True).stdout
    # Historical runs may have empty patches from the collector defect (#76).
    # Scope inventories above remain the required sealed content authority.
    if patch and patch != actual:
        raise WorkflowError("sealed task patch does not match commit")
    return actual


def integrate(settings: Settings, repo: Path, *, run_ids: list[str], commands_file: Path,
              dest: Path, output: Path, actor: str, reason: str) -> dict[str, Any]:
    """Validate accepted task commits, apply in order, and record replay evidence."""
    repo = _git_root(repo)
    dest, output, commands_file = dest.resolve(), output.resolve(), commands_file.resolve()
    receipt_path = output / "integration-receipt.json"
    request = {"repo": str(repo), "run_ids": run_ids, "commands_file": str(commands_file),
               "commands_sha256": _sha(commands_file), "dest": str(dest), "actor": actor, "reason": reason}
    request_hash = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if output.exists():
        if receipt_path.is_file():
            old = _json(receipt_path)
            if old.get("request_sha256") == request_hash:
                verify_integration(output)
                if old.get("status") != "success":
                    raise WorkflowError("integration attempt was rejected; use a new output directory to retry")
                return old
        raise WorkflowError("output directory already exists for a different integration request")
    # Refuse path mistakes before creating even diagnostic files in source trees.
    protected = [Path(row["worktree"]).resolve() for row in list_worktrees(repo)]
    protected.extend([common_administrative_dir(repo), settings.state_root.resolve()])
    if (any(dest.is_relative_to(root) or output.is_relative_to(root) for root in protected)
            or dest.is_relative_to(output) or output.is_relative_to(dest)):
        raise WorkflowError("destination/evidence must be disjoint and outside source, run and Git storage")
    output.mkdir(parents=True, mode=0o700)
    worktree_created = False
    record: dict[str, Any] = {"schema": SCHEMA, "created_at": utc_now(), "request": request,
        "request_sha256": request_hash, "status": "rejected", "decision": "rejected", "inputs": [], "commands": []}
    try:
        if len(run_ids) != 2 or len(set(run_ids)) != 2:
            raise WorkflowError("exactly two distinct task runs are required")
        if not actor.strip() or not reason.strip():
            raise WorkflowError("actor and reason are required")
        _idle(repo)
        if not _clean(repo):
            raise WorkflowError("repository must be clean")
        inputs = [_accepted_run(settings, repo, run_id) for run_id in run_ids]
        if len({item["baseline"] for item in inputs}) != 1 or len({(item["source"].get("source_sha256"), item["source"].get("stored_sha256")) for item in inputs}) != 1:
            raise WorkflowError("input runs do not share the frozen source specification and baseline")
        if len({item["task_id"] for item in inputs}) != 2 or len({item["head"] for item in inputs}) != 2:
            raise WorkflowError("input tasks and commits must be unique")
        if len({item["binding"].get("ticket_id") for item in inputs}) != 2 or any(item["binding"].get("job_id") != item["task_id"] for item in inputs):
            raise WorkflowError("sealed task, ticket, and job identities do not match")
        commands = _validate_command_file(commands_file)
        commands_bytes = read_regular_file(commands_file).data
        if hashlib.sha256(commands_bytes).hexdigest() != request["commands_sha256"]:
            raise WorkflowError("commands file changed during integration preparation")
        (output / "commands.json").write_bytes(commands_bytes)
        base = inputs[0]["baseline"]
        record["inputs"] = [{k: item[k] for k in ("run_id", "seal_sha256", "binding_sha256", "completion_sha256", "task_id", "baseline", "head", "commit", "changed_paths", "scope")} for item in inputs]
        record.update({"base_revision": base, "actor": actor, "reason": reason,
                       "source_specification_sha256": inputs[0]["source"]["stored_sha256"],
                       "commands_policy_sha256": _sha(commands_file), "commands_policy": commands})
        for item in inputs:
            input_root = output / "inputs" / item["run_id"]
            input_root.mkdir(parents=True)
            final_receipt = verify_seal_details(item["run_dir"])[0]
            for artifact in final_receipt["artifacts"]:
                name = artifact["path"]
                data, _ = read_sealed_artifact_bytes(item["run_dir"], final_receipt, name)
                target = input_root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            (input_root / "final-receipt.json").write_bytes((item["run_dir"] / "final-receipt.json").read_bytes())
            for entry in lifecycle_receipts(item["run_dir"], expected_final_receipt_sha256=item["seal_sha256"]):
                target = input_root / "receipts" / entry["path"].name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(entry["path"].read_bytes())
            (input_root / "input-commit.diff").write_bytes(_validate_diff_evidence(
                repo, item["run_dir"], final_receipt, item["binding"], item["completion"]))
            _git(Path(item["binding"]["worktree"]), "bundle", "create", str(input_root / "source.bundle"), "HEAD")
        if dest.exists():
            raise WorkflowError("destination worktree already exists")
        if dest.resolve().is_relative_to(repo) or output.resolve().is_relative_to(repo):
            raise WorkflowError("destination and evidence must be outside source repository")
        if dest.resolve().is_relative_to(output.resolve()) or output.resolve().is_relative_to(dest.resolve()):
            raise WorkflowError("destination and evidence directories must be separate")
        dest.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "--detach", str(dest), base)
        worktree_created = True
        env = _COMMIT_ENV
        record["applied"] = []
        for item in inputs:
            result = _git(dest, "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "cherry-pick", "-x", item["head"], check=False, env=env)
            if not result.ok:
                record.setdefault("git_failures", []).append({"operation": "cherry-pick", "original": item["head"], "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
                raise WorkflowError(f"cherry-pick failed for {item['head']}")
            record["applied"].append({"original": item["head"], "applied": str(_git(dest, "rev-parse", "HEAD").stdout).strip(),
                                      "commit": _commit(dest, "HEAD")})
        record["head_revision"] = str(_git(dest, "rev-parse", "HEAD").stdout).strip()
        record["tree_revision"] = str(_git(dest, "rev-parse", "HEAD^{tree}").stdout).strip()
        record["changed_paths"] = sorted(str(_git(dest, "diff", "--name-only", base, "HEAD").stdout).splitlines())
        record["commands"] = []
        for command in commands:
            cwd = (dest / command["cwd"]).resolve()
            if not cwd.is_relative_to(dest) or not cwd.is_dir():
                raise WorkflowError(f"command cwd is not a directory within integration worktree: {command['id']}")
            before = str(_git(dest, "rev-parse", "HEAD").stdout).strip()
            result = run(command["argv"], cwd=cwd, check=False, timeout_seconds=command["timeout_seconds"],
                         environment=EnvironmentPolicy(values={"PYTHONDONTWRITEBYTECODE": "1"}, unsafe_inherit=True))
            after = str(_git(dest, "rev-parse", "HEAD").stdout).strip()
            dirty = not _clean(dest)
            row = {"id": command["id"], "argv": command["argv"], "cwd": command["cwd"], "returncode": result.returncode,
                   "process": result.as_dict(), "stdout": result.stdout, "stderr": result.stderr, "timed_out": result.timed_out, "head_before": before, "head_after": after, "dirty_after": dirty}
            record["commands"].append(row)
            if not result.ok or result.stdout_truncated or result.stderr_truncated or before != after or dirty:
                raise WorkflowError(f"combined acceptance command failed or mutated integration result: {command['id']}")
        bundle = output / "integration.bundle"
        _git(dest, "bundle", "create", str(bundle), "HEAD")
        record["bundle_sha256"] = _sha(bundle)
        record["worktree"] = str(dest)
        record["status"], record["decision"] = "success", "accepted"
    except Exception as exc:
        record["error"] = str(exc)
        if worktree_created:
            rollback = _git(repo, "worktree", "remove", "--force", str(dest), check=False)
            record["rollback"] = rollback.as_dict()
            worktree_created = False
    artifacts = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "integration-receipt.json":
            artifacts.append({"path": path.relative_to(output).as_posix(), "sha256": _sha(path), "size": path.stat().st_size})
            path.chmod(0o444)
    record["artifacts"] = artifacts
    record["receipt_sha256"] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    validate_instance(record, SCHEMA, artifact="integration receipt")
    _write_immutable_json(receipt_path, record)
    if record["status"] != "success":
        raise WorkflowError(record["error"])
    return record


def verify_integration(evidence_dir: Path) -> dict[str, Any]:
    """Verify archived bytes, input seals/acceptance, and deterministic Git replay.

    Verification does not rerun host acceptance commands or consult live workers.
    All mutable Git/lock operations happen in invocation-owned temporary storage.
    """
    evidence_dir = evidence_dir.resolve()
    receipt = _json(evidence_dir / "integration-receipt.json")
    validate_instance(receipt, SCHEMA, artifact="integration receipt")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    if receipt["receipt_sha256"] != hashlib.sha256(canonical).hexdigest():
        raise WorkflowError("integration receipt canonical hash mismatch")
    request_hash = hashlib.sha256(json.dumps(receipt["request"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if request_hash != receipt["request_sha256"]:
        raise WorkflowError("integration request hash mismatch")
    paths = set()
    for item in receipt["artifacts"]:
        relative = item["path"]
        if (not _relative_path(relative) or relative in paths
                or not (evidence_dir / relative).resolve().is_relative_to(evidence_dir)):
            raise WorkflowError("unsafe or duplicate integration evidence path")
        paths.add(relative)
        read = read_regular_file(evidence_dir / relative)
        if len(read.data) != item["size"] or read.sha256 != item["sha256"]:
            raise WorkflowError(f"integration evidence artifact mismatch: {relative}")
    if receipt["status"] == "rejected":
        if receipt["decision"] != "rejected" or not receipt.get("error"):
            raise WorkflowError("invalid rejected integration decision")
        return receipt
    inputs = receipt["inputs"]
    if (receipt["decision"] != "accepted" or len(inputs) != 2
            or len({item["run_id"] for item in inputs}) != 2
            or len({item["task_id"] for item in inputs}) != 2
            or len({item["head"] for item in inputs}) != 2
            or any(item["baseline"] != receipt["base_revision"] for item in inputs)
            or [item["run_id"] for item in inputs] != receipt["request"]["run_ids"]):
        raise WorkflowError("invalid successful integration inputs/decision")
    if (_sha(evidence_dir / "commands.json") != receipt["commands_policy_sha256"]
            or _sha(evidence_dir / "commands.json") != receipt["request"]["commands_sha256"]
            or _json(evidence_dir / "commands.json") != receipt["commands_policy"]
            or len(receipt["commands"]) != len(receipt["commands_policy"])):
        raise WorkflowError("integration command policy mismatch")
    for result, command in zip(receipt["commands"], receipt["commands_policy"]):
        if (result["id"] != command["id"] or result["argv"] != command["argv"]
                or result["returncode"] != 0 or result["timed_out"] or result["dirty_after"]
                or result["head_before"] != receipt["head_revision"]
                or result["head_after"] != receipt["head_revision"]):
            raise WorkflowError("integration command evidence does not pass at combined revision")
    with tempfile.TemporaryDirectory(prefix="agent-workflow-integration-verify-") as temporary:
        scratch = Path(temporary)
        git = scratch / "replay"
        git.mkdir()
        _git(git, "init", "-q")
        for item in inputs:
            archive = evidence_dir / "inputs" / item["run_id"]
            snapshot = scratch / item["run_id"]
            shutil.copytree(archive, snapshot)
            final, digest = verify_seal_details(snapshot, expected_sha256=item["seal_sha256"])
            binding, binding_hash = read_sealed_json(snapshot, final, "job-binding.json")
            completion, completion_hash = read_sealed_json(snapshot, final, "completion.json")
            source, source_hash = read_sealed_json(snapshot, final, "jobs/source-specification.json")
            if (digest != item["seal_sha256"] or binding_hash != item["binding_sha256"]
                    or completion_hash != item["completion_sha256"]
                    or source_hash != receipt["source_specification_sha256"]
                    or binding["source_specification"]["task_refs"] != [item["task_id"]]
                    or binding["job_id"] != item["task_id"]
                    or completion["ticket_id"] != item["task_id"]
                    or completion["head_revision"] != item["head"]
                    or source["repository"]["revision"] != item["baseline"]
                    or binding["scope"] != item["scope"]):
                raise WorkflowError("archived task binding disagrees with integration receipt")
            chain = lifecycle_receipts(snapshot, expected_final_receipt_sha256=digest)
            if (len(chain) < 2 or chain[-1]["receipt"]["action"] != "accepted"
                    or chain[-2]["receipt"]["action"] != "reviewed"
                    or chain[-1]["receipt"]["revision"] != item["head"]):
                raise WorkflowError("archived task lacks host acceptance")
            _git(git, "fetch", str(archive / "source.bundle"), "HEAD")
            if _git(git, "rev-parse", "FETCH_HEAD").stdout.strip() != item["head"]:
                raise WorkflowError("input bundle head mismatch")
            actual = _validate_diff_evidence(git, snapshot, final, binding, completion)
            if (read_regular_file(archive / "input-commit.diff").data != actual
                    or _commit(git, item["head"])["parents"] != item["baseline"]):
                raise WorkflowError("input Git commit disagrees with source evidence/baseline")
        _git(git, "checkout", "--detach", receipt["base_revision"])
        for item, applied in zip(inputs, receipt["applied"]):
            _git(git, "cherry-pick", "-x", item["head"], env=_COMMIT_ENV)
            if (applied["original"] != item["head"]
                    or _git(git, "rev-parse", "HEAD").stdout.strip() != applied["applied"]):
                raise WorkflowError("deterministic integration replay mismatch")
        if (_git(git, "rev-parse", "HEAD").stdout.strip() != receipt["head_revision"]
                or _git(git, "rev-parse", "HEAD^{tree}").stdout.strip() != receipt["tree_revision"]):
            raise WorkflowError("combined Git revision/tree mismatch")
        _git(git, "fetch", str(evidence_dir / "integration.bundle"), "HEAD")
        if _git(git, "rev-parse", "FETCH_HEAD").stdout.strip() != receipt["head_revision"]:
            raise WorkflowError("combined bundle head mismatch")
    return receipt
