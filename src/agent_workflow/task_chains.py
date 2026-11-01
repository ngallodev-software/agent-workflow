"""Bounded host coordination over existing Agent Runs and integration receipts.

No worker execution, review or acceptance is implicit in these operations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .contracts import validate_instance
from .receipts import _seal_lock
from .repository_closeout import _write_immutable_json
from .state import run_dir
from .util import utc_now, validate_id
from . import task_integration as integration

PLAN = "agent-workflow/task-chain/v1"
BINDING = "agent-workflow/execution-binding/v1"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def order_tasks(tasks: list[dict[str, Any]]) -> list[str]:
    ids = [item["task_id"] for item in tasks]
    if not ids or len(set(ids)) != len(ids):
        raise WorkflowError("task chain requires unique task identities")
    pending = {item["task_id"]: set(item["predecessors"]) for item in tasks}
    if any(task in deps or not deps <= set(ids) for task, deps in pending.items()):
        raise WorkflowError("missing predecessor or self-dependency")
    order: list[str] = []
    while pending:
        ready = sorted(task for task, deps in pending.items() if deps <= set(order))
        if not ready:
            raise WorkflowError("cyclic task dependencies")
        # Sequential, lexicographically stable Kahn ordering; no scheduling guesses.
        task = ready[0]
        order.append(task)
        del pending[task]
    return order


def validate_plan(plan: dict[str, Any]) -> list[str]:
    validate_instance(plan, PLAN, artifact="task chain plan")
    if plan["plan_sha256"] != digest({k: v for k, v in plan.items() if k != "plan_sha256"}):
        raise WorkflowError("task chain plan hash mismatch")
    order = order_tasks(plan["tasks"])
    if order != plan["order"]:
        raise WorkflowError("task chain order mismatch")
    return order


def validate_execution_binding(value, job=None, run_id=None, workdir=None):
    validate_instance(value, BINDING, artifact="execution binding")
    plan = value["plan"]
    order = validate_plan(plan)
    task = value["task_id"]
    if task not in order:
        raise WorkflowError("execution task is absent from chain")
    index = order.index(task)
    prior = value["prior_integration"]
    if index == 0:
        expected = plan["planning_revision"]
        if prior is not None:
            raise WorkflowError("first task cannot have predecessor integration")
    else:
        if not isinstance(prior, dict):
            raise WorkflowError("missing accepted predecessor integration")
        integration._verify_receipt_hash(prior)
        if (prior["schema"] != "agent-workflow/task-integration/v2"
                or prior["status"] != "success" or prior["decision"] != "accepted"
                or prior["purpose"] != "transition" or prior["chain_plan"] != plan
                or [row["task_id"] for row in prior["inputs"]] != order[:index]):
            raise WorkflowError("execution baseline lacks accepted predecessor prefix")
        expected = prior["head_revision"]
    if value["execution_revision"] != expected:
        raise WorkflowError("incorrect or stale execution baseline")
    if job is not None:
        row = next(row for row in plan["tasks"] if row["task_id"] == task)
        if (job.schema != "agent-workflow/native-job/v2" or job.job_id != task
                or job.ticket_id != task or job.source_specification.task_refs != (task,)
                or job.job_sha256 != row["job_sha256"]
                or job.source_specification.sha256 != plan["source_specification_sha256"]
                or job.source_specification.receipt["repository"]["revision"] != plan["planning_revision"]
                or value["run_id"] != run_id or value["worktree"] != str(workdir)):
            raise WorkflowError("execution binding differs from frozen task/job/source/run identity")
    return value


def validate_prefix(plan, inputs, bindings):
    """Validate an archived or live contiguous accepted prefix, without live paths."""
    order = validate_plan(plan)
    if not inputs or [item["task_id"] for item in inputs] != order[:len(inputs)]:
        raise WorkflowError("integration inputs are not the deterministic task prefix")
    baseline = plan["planning_revision"]
    for index, (item, authority) in enumerate(zip(inputs, bindings, strict=True)):
        validate_execution_binding(authority)
        if (authority["plan"] != plan or authority["task_id"] != item["task_id"]
                or authority["run_id"] != item["run_id"]
                or authority["execution_revision"] != baseline or item["baseline"] != baseline):
            raise WorkflowError("task execution baseline or chain identity mismatch")
        if index:
            prior = authority["prior_integration"]
            keys = ("run_id", "seal_sha256", "binding_sha256", "completion_sha256", "task_id", "baseline", "head", "changed_paths", "scope", "commit")
            if any(any(old[key] != new[key] for key in keys) for old, new in zip(prior["inputs"], inputs[:index], strict=True)):
                raise WorkflowError("predecessor integration disagrees with sealed accepted inputs")
            if prior["head_revision"] != baseline:
                raise WorkflowError("predecessor integrated revision mismatch")
        baseline = item["head"]


def create(settings, repo: Path, *, pack: Path, dependencies: Path, commands: Path,
           final_commands: Path, output: Path, actor: str, reason: str, tier: str):
    from .native_jobs import validate_native_job
    repo, pack, output = integration._git_root(repo), pack.resolve(), output.resolve()
    protected = [Path(row["worktree"]).resolve() for row in integration.list_worktrees(repo)]
    protected += [integration.common_administrative_dir(repo), settings.state_root.resolve()]
    if any(output.is_relative_to(root) for root in protected):
        raise WorkflowError("chain storage must be outside source, run and Git storage")
    if output.exists():
        raise WorkflowError("chain storage already exists")
    integration._idle(repo)
    if not integration._clean(repo):
        raise WorkflowError("repository must be clean")
    deps = integration._json(dependencies)
    source = integration._json(pack / "source-specification.json")
    pending = {item["agent_workflow_task_id"] for item in source["task_map"] if not item["done_at_import"]}
    if not isinstance(deps, dict) or not deps or not set(deps) <= pending:
        raise WorkflowError("dependencies must map imported pending task IDs to predecessor arrays")
    tasks = []
    for task, predecessors in sorted(deps.items()):
        if (not isinstance(predecessors, list) or any(not isinstance(p, str) for p in predecessors)
                or len(set(predecessors)) != len(predecessors)):
            raise WorkflowError("predecessors must be unique task ID arrays")
        job = validate_native_job(pack / "jobs" / f"{task}.json", pack_root=pack)
        from .native_jobs import validate_source_specification_worktree
        validate_source_specification_worktree(job, repo)
        if job.job_id != task or job.ticket_id != task or job.source_specification.task_refs != (task,):
            raise WorkflowError("job does not match imported task identity")
        tasks.append({"task_id": task, "predecessors": sorted(predecessors), "job_sha256": job.job_sha256})
    plan = {"schema": PLAN, "created_at": utc_now(), "repo": str(repo), "pack": str(pack),
            "planning_revision": source["repository"]["revision"],
            "source_specification_sha256": integration._sha(pack / "source-specification.json"),
            "tasks": tasks, "order": order_tasks(tasks),
            "transition_commands": integration._validate_command_file(commands),
            "final_commands": integration._validate_command_file(final_commands),
            "actor": actor, "reason": reason, "tier": tier}
    if not actor.strip() or not reason.strip():
        raise WorkflowError("actor and reason are required")
    plan["plan_sha256"] = digest(plan)
    validate_plan(plan)
    output.mkdir(mode=0o700, parents=True)
    _write_immutable_json(output / "plan.json", plan)
    return plan


def _state(settings, root):
    plan = integration._json(root / "plan.json")
    order = validate_plan(plan)
    prefix = []
    reservations = []
    gap = False
    for index, task in enumerate(order):
        reservation_path = root / f"task-{index:04d}.json"
        attempt = root / f"integration-{index:04d}"
        if not reservation_path.exists():
            gap = True
            if attempt.exists():
                raise WorkflowError("integration without task reservation")
            continue
        if gap:
            raise WorkflowError("inconsistent recovered chain: reservation after gap")
        reservation = integration._json(reservation_path)
        validate_execution_binding(reservation)
        if reservation["plan"] != plan or reservation["task_id"] != task:
            raise WorkflowError("reservation disagrees with plan")
        if index and len(prefix) != index:
            raise WorkflowError("reservation without accepted predecessor")
        if reservation["prior_integration"] != (prefix[-1] if prefix else None):
            raise WorkflowError("reservation predecessor evidence mismatch")
        reservations.append(reservation)
        if attempt.exists():
            receipt = integration.verify_integration(attempt)
            if (receipt["status"] != "success" or receipt["purpose"] != "transition"
                    or receipt["chain_plan"] != plan
                    or receipt["request"]["run_ids"] != [r["run_id"] for r in reservations]):
                raise WorkflowError("chain transition is invalid or rejected")
            prefix.append(receipt)
    if len({r["run_id"] for r in reservations}) != len(reservations):
        raise WorkflowError("duplicate reserved run")
    final = None
    if (root / "final").exists():
        final = integration.verify_integration(root / "final")
        if (len(prefix) != len(order) or final["status"] != "success"
                or final["purpose"] != "final" or final["chain_plan"] != plan
                or final["request"]["run_ids"] != [r["run_id"] for r in reservations]):
            raise WorkflowError("invalid or failed combined chain acceptance")
    return plan, reservations, prefix, final


def operate(settings, root: Path, *, action: str, run_id=None, worker=None):
    root = root.resolve()
    if not root.is_dir():
        raise WorkflowError("chain storage is unavailable")
    with _seal_lock(root, exclusive=True):
        plan, reservations, prefix, final = _state(settings, root)
        if action == "status":
            return {"plan_sha256": plan["plan_sha256"], "order": plan["order"],
                    "reservations": reservations, "accepted_tasks": len(prefix),
                    "final_accepted": final is not None,
                    "execution_revision": prefix[-1]["head_revision"] if prefix else plan["planning_revision"]}
        if final is not None:
            raise WorkflowError("chain is already finally accepted")
        index = len(prefix)
        if action == "prepare":
            if index >= len(plan["order"]):
                raise WorkflowError("all tasks are already accepted")
            if len(reservations) != index:
                raise WorkflowError("task already reserved; recover the recorded run, do not execute twice")
            validate_id(run_id, "agent run ID")
            if run_dir(settings, run_id).exists():
                raise WorkflowError("run already exists")
            if not worker:
                raise WorkflowError("an explicit fixture/provider worker command is required")
            task = plan["order"][index]
            repo, pack = Path(plan["repo"]), Path(plan["pack"])
            integration._idle(repo)
            if not integration._clean(repo):
                raise WorkflowError("repository must be clean")
            # Revalidate original accepted worktrees/seals at each transition.
            for reservation in reservations:
                integration._accepted_run(settings, repo, reservation["run_id"], allow_dependent=True)
            worktree = root.parent / f"{root.name}-task-{index:04d}"
            if worktree.exists():
                raise WorkflowError("task worktree already exists; dirty/reused worktrees are prohibited")
            baseline = prefix[-1]["head_revision"] if prefix else plan["planning_revision"]
            binding = {"schema": BINDING, "plan": plan, "task_id": task, "run_id": run_id,
                       "worktree": str(worktree), "execution_revision": baseline,
                       "prior_integration": prefix[-1] if prefix else None}
            from .native_jobs import validate_native_job
            job = validate_native_job(pack / "jobs" / f"{task}.json", pack_root=pack)
            validate_execution_binding(binding, job, run_id, worktree)
            # Reserve BEFORE side effects: a crash fails closed, never starts a duplicate.
            _write_immutable_json(root / f"task-{index:04d}.json", binding)
            integration._git(repo, "worktree", "add", "--detach", str(worktree), baseline)
            from .agent_runs import prepare
            result = prepare(settings, agent_run_id=run_id, workdir=worktree,
                             prompt_path=job.prompt_path, pack_id=str(pack), job_path=job.job_path,
                             tier=plan["tier"], worker_mode="external", interactive=True,
                             explicit_command=worker, execution_binding=binding)
            return result
        if action not in {"advance", "accept"}:
            raise WorkflowError("unsupported chain operation")
        if action == "advance":
            if len(reservations) != index + 1:
                raise WorkflowError("no unintegrated reserved task; duplicate advancement refused")
            dest = root.parent / f"{root.name}-integrated-{index:04d}"
            output = root / f"integration-{index:04d}"
            commands = plan["transition_commands"]
            purpose = "transition"
        else:
            if index != len(plan["order"]):
                raise WorkflowError("all tasks must be accepted before combined acceptance")
            dest = root.parent / f"{root.name}-final"
            output = root / "final"
            commands, purpose = plan["final_commands"], "final"
        for reservation in reservations:
            integration._accepted_run(settings, Path(plan["repo"]), reservation["run_id"], allow_dependent=True)
        commands_file = root / f"{purpose}-commands.json"
        if not commands_file.exists():
            _write_immutable_json(commands_file, commands)
        elif integration._json(commands_file) != commands:
            raise WorkflowError("chain command policy changed")
        return integration.integrate(settings, Path(plan["repo"]),
            run_ids=[r["run_id"] for r in reservations], commands_file=commands_file,
            dest=dest, output=output, actor=plan["actor"], reason=plan["reason"],
            chain_plan=plan, purpose=purpose)


def validate_launch(directory: Path) -> None:
    """Recheck v3 authority at host start/dispatch; legacy launch is unchanged."""
    from .contracts import read_contract
    from .native_jobs import validate_native_job, validate_source_specification_worktree
    from .receipts import verify_seal_details
    from .lifecycle import lifecycle_receipts
    binding_path = directory / "job-binding.json"
    if not binding_path.exists():
        return
    binding = read_contract(binding_path)
    if binding["schema"] != "agent-workflow/job-binding/v3":
        return
    authority_path = directory / "jobs/execution-binding.json"
    authority = read_contract(authority_path, BINDING)
    if integration._sha(authority_path) != binding["execution_binding_sha256"]:
        raise WorkflowError("launch execution binding checksum mismatch")
    worktree = Path(binding["worktree"])
    job = validate_native_job(Path(binding["job_source_path"]), pack_root=Path(binding["pack_root"]))
    validate_execution_binding(authority, job, directory.name, worktree)
    if integration.common_administrative_dir(worktree) != integration.common_administrative_dir(Path(authority["plan"]["repo"])):
        raise WorkflowError("launch repository identity mismatch")
    integration._idle(worktree)
    validate_source_specification_worktree(job, worktree, execution_revision=authority["execution_revision"])
    prior = authority["prior_integration"]
    for item in prior["inputs"] if prior else []:
        predecessor = directory.parent / item["run_id"]
        _, seal = verify_seal_details(predecessor, expected_sha256=item["seal_sha256"])
        receipts = lifecycle_receipts(predecessor, expected_final_receipt_sha256=seal)
        if (len(receipts) < 2 or receipts[-1]["receipt"]["action"] != "accepted"
                or receipts[-2]["receipt"]["action"] != "reviewed"
                or receipts[-1]["receipt"]["revision"] != item["head"]):
            raise WorkflowError("launch predecessor is no longer verifiably accepted")
