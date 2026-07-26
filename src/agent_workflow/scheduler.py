from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import Settings
from .approval import lifecycle_disposition
from .bindings import resolve_node_inputs
from .contracts import read_contract, validate_instance
from .errors import WorkflowError
from .receipts import (
    read_sealed_contract,
    update_provenance,
    verify_seal,
    verify_seal_details,
)
from .routing import advise_routing
from .sessions import launch as launch_session
from .util import validate_id
from .workflow import (
    ensure_workflow_events_file,
    reconstruct_workflow_status,
    record_workflow_binding,
    record_workflow_transition,
    snapshot_sha256,
    workflow_events_path,
    workflow_lock,
)
from .state import run_dir as session_run_dir


LaunchFunction = Callable[[Mapping[str, Any], str], Any]


@dataclass(frozen=True)
class LaunchPlan:
    """A durable node binding selected for one scheduler attempt."""

    node_id: str
    run_id: str
    attempt: int
    retry_of_run_id: str | None = None


def calculate_eligibility(
    snapshot: Mapping[str, Any], status: Mapping[str, Any]
) -> list[str]:
    """Return nodes that may be launched, in deterministic graph order.

    Failed prerequisites intentionally leave their dependents blocked.  A
    retry must first make the prerequisite successful; there is no implicit
    retry policy in this service.
    """
    nodes = {str(node["node_id"]): node for node in snapshot["nodes"]}
    states = {str(node["node_id"]): str(node["state"]) for node in status["nodes"]}
    return sorted(
        node_id
        for node_id, node in nodes.items()
        if states.get(node_id) == "eligible"
        and all(states.get(dep) == "completed" for dep in node["dependencies"])
    )


def plan_launches(
    snapshot: Mapping[str, Any],
    status: Mapping[str, Any],
    *,
    max_parallelism: int,
) -> list[str]:
    """Select eligible task nodes without exceeding total active capacity."""
    if isinstance(max_parallelism, bool) or max_parallelism < 1:
        raise WorkflowError("max_parallelism must be a positive integer")
    running = sum(
        1
        for node in status["nodes"]
        if str(node.get("state")) == "running"
    )
    capacity = max(0, max_parallelism - running)
    if capacity == 0:
        return []
    node_map = {str(node["node_id"]): node for node in snapshot["nodes"]}
    return [
        node_id
        for node_id in calculate_eligibility(snapshot, status)
        if node_map[node_id].get("kind", "task") == "task"
    ][:capacity]


class SchedulerService:
    """Restart-safe dependency scheduler backed by the workflow event journal."""

    def __init__(
        self,
        *,
        settings: Settings,
        run_dir: Path,
        workdir: Path,
        max_parallelism: int = 1,
        launch_fn: LaunchFunction | None = None,
        actor: str = "scheduler",
    ) -> None:
        if isinstance(max_parallelism, bool) or max_parallelism < 1:
            raise WorkflowError("max_parallelism must be a positive integer")
        self.settings = settings
        self.run_dir = Path(run_dir)
        self.workdir = Path(workdir)
        self.max_parallelism = max_parallelism
        self.launch_fn = launch_fn or self._launch
        self.actor = actor

    def _launch(self, node: Mapping[str, Any], run_id: str) -> Any:
        prompt = Path(str(node["prompt_path"]))
        if not prompt.is_absolute():
            prompt = self.workdir / prompt
        explicit = {
            key: node.get(key)
            for key in ("agent_class", "executor", "model", "interactive")
            if node.get(key) is not None
        }
        advice = advise_routing(
            node.get("routing") if isinstance(node.get("routing"), Mapping) else {},
            self.settings,
            enforced_selection=explicit,
        )
        validate_instance(advice, advice["schema"], artifact="workflow routing advice")
        selected = advice["enforced_selection"]
        result = launch_session(
            self.settings,
            session_id=run_id,
            workdir=self.workdir,
            prompt_path=prompt,
            ticket_id=str(node["ticket_id"]) if node.get("ticket_id") else None,
            pack_id=str(node["pack_id"]) if node.get("pack_id") else None,
            retry_of=str(node["retry_of_run_id"]) if node.get("retry_of_run_id") else None,
            tier=str(node["tier"]) if node.get("tier") else None,
            executor=str(selected["executor"]),
            agent_class=str(selected["agent_class"]),
            model=str(selected["model"]),
            interactive=bool(selected["interactive"]),
            allow_no_go_model=bool(node.get("allow_no_go_model", False)),
            workflow_context=(
                node["workflow_inputs"]["artifact"]
                if isinstance(node.get("workflow_inputs"), Mapping)
                else None
            ),
        )
        child_dir = session_run_dir(self.settings, run_id)
        command = read_contract(child_dir / "command.json", "agent-workflow/command/v1")
        actual = {
            "agent_class": command.get("agent_class"),
            "executor": command.get("executor"),
            "model": command.get("model"),
            "interactive": command.get("interactive"),
        }
        routing_record = dict(advice)
        routing_record["actual_selection"] = actual
        routing_record["policy_disagreements"] = sorted(
            key
            for key in advice["recommendation"]
            if advice["recommendation"][key] != actual.get(key)
        )
        provenance = read_contract(
            child_dir / "run-provenance.json", "agent-workflow/run-provenance/v1"
        )
        workflow = dict(provenance.get("workflow") or {})
        workflow.setdefault("workflow_id", str(node["workflow_id"]))
        workflow.setdefault("node_id", str(node["node_id"]))
        workflow.setdefault("attempt", int(node["workflow_attempt"]))
        workflow.setdefault("inputs_path", None)
        workflow.setdefault("inputs_sha256", None)
        workflow["routing"] = routing_record
        try:
            update_provenance(child_dir, workflow=workflow)
        except WorkflowError as exc:
            if not (child_dir / "final-receipt.json").is_file():
                raise
            # The detached child sealed before routing enrichment acquired the
            # seal lock. Its immutable receipt is authoritative already.
            if "cannot update sealed provenance" not in str(exc):
                raise
        return result

    @staticmethod
    def _run_id(workflow_id: str, node: Mapping[str, Any], attempt: int) -> str:
        base = str(node["session_id"])
        run_id = base if attempt == 1 else f"{base}-retry-{attempt}"
        return validate_id(run_id, "workflow run ID")

    def status(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        events_path = ensure_workflow_events_file(self.run_dir)
        return reconstruct_workflow_status(snapshot, events_path)

    def _child_run_exists(self, run_id: str) -> bool:
        """Return whether a child has a real run footprint outside workflow events.

        The workflow journal may record that a launch once existed, but it cannot
        prove that the child evidence still exists. Mutable ``status.json`` is
        also only a projection. A matching provenance contract is the minimum
        durable launch footprint; a valid final receipt is stronger evidence.
        """
        child = session_run_dir(self.settings, run_id)
        try:
            info = child.lstat()
        except OSError:
            return False
        if child.is_symlink() or not child.is_dir():
            return False
        final_receipt = child / "final-receipt.json"
        if final_receipt.exists() or final_receipt.is_symlink():
            try:
                receipt = verify_seal(child)
            except WorkflowError:
                # A detached child may publish the receipt before its final
                # artifact set is visible. Provenance is the minimum launch
                # authority; terminal reconciliation still requires a valid
                # sealed receipt.
                pass
            else:
                return receipt.get("session_id") == run_id
        provenance_path = child / "run-provenance.json"
        if provenance_path.is_symlink() or not provenance_path.is_file():
            return False
        try:
            provenance = read_contract(
                provenance_path, "agent-workflow/run-provenance/v1"
            )
        except WorkflowError:
            return False
        return provenance.get("session_id") == run_id

    def _terminal_child_outcome(self, run_id: str) -> tuple[str, str, dict[str, Any]] | None:
        """Return a verified terminal workflow transition for a sealed child."""
        child = session_run_dir(self.settings, run_id)
        receipt_path = child / "final-receipt.json"
        if not receipt_path.exists() and not receipt_path.is_symlink():
            return None
        receipt, receipt_digest = verify_seal_details(child)
        if receipt.get("session_id") != run_id:
            raise WorkflowError(f"child final receipt belongs to another run: {run_id}")
        final_status, _ = read_sealed_contract(
            child,
            receipt,
            "final-status.json",
            "agent-workflow/session-status/v2",
        )
        completion, completion_digest = read_sealed_contract(
            child,
            receipt,
            "completion.json",
            "agent-workflow/completion/v1",
        )
        collection, _ = read_sealed_contract(
            child,
            receipt,
            "collections/completion.json",
            "agent-workflow/completion-collection/v1",
        )
        if final_status.get("session_id") != run_id or completion.get("session_id") != run_id:
            raise WorkflowError(f"child terminal evidence belongs to another run: {run_id}")
        completed = (
            final_status.get("status") == "completed"
            and completion.get("result") == "completed"
            and collection.get("validation_status") == "valid"
        )
        details = {
            "child_run_id": run_id,
            "child_final_receipt_sha256": receipt_digest,
            "child_completion_sha256": completion_digest,
            "child_status": final_status.get("status"),
            "child_completion_result": completion.get("result"),
            "child_completion_validation_status": collection.get("validation_status"),
        }
        if completed:
            return "completed", "sealed child run completed successfully", details
        return "failed", "sealed child run did not satisfy completion evidence", details

    def _reconcile_running(self, snapshot: Mapping[str, Any], status: Mapping[str, Any]) -> None:
        digest = snapshot_sha256(snapshot)
        node_map = {str(node["node_id"]): node for node in snapshot["nodes"]}
        for current in status["nodes"]:
            if current.get("state") != "running":
                continue
            node_id = str(current["node_id"])
            if node_map[node_id].get("kind", "task") != "task":
                raise WorkflowError(f"approval node cannot be running: {node_id}")
            run_id = current.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason="running node has no authoritative child run binding",
                    snapshot_sha256=digest,
                    previous_state="running",
                    next_state="recoverable",
                )
                continue
            try:
                outcome = self._terminal_child_outcome(run_id)
            except WorkflowError as exc:
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason=f"child terminal evidence failed verification: {exc}",
                    snapshot_sha256=digest,
                    previous_state="running",
                    next_state="failed",
                    details={"child_run_id": run_id},
                )
                continue
            if outcome is not None:
                next_state, reason, details = outcome
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason=reason,
                    snapshot_sha256=digest,
                    previous_state="running",
                    next_state=next_state,
                    details=details,
                )
            elif not self._child_run_exists(run_id):
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason="running state has no authoritative child run; recovery required",
                    snapshot_sha256=digest,
                    previous_state="running",
                    next_state="recoverable",
                    details={"child_run_id": run_id},
                )

    def _reconcile_blocked(self, snapshot: Mapping[str, Any], status: Mapping[str, Any]) -> None:
        status_map = {str(item["node_id"]): item for item in status["nodes"]}
        states = {node_id: str(item["state"]) for node_id, item in status_map.items()}
        digest = snapshot_sha256(snapshot)
        for node in snapshot["nodes"]:
            node_id = str(node["node_id"])
            current = status_map[node_id]
            failed_dependencies = [
                dep for dep in node["dependencies"] if states.get(dep) == "failed"
            ]
            dependency_failure = str(current.get("terminal_reason") or "").startswith(
                "workflow prerequisite failed:"
            )
            if states.get(node_id) == "failed" and dependency_failure and not failed_dependencies:
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason="workflow prerequisite retry reopened dependency gate",
                    snapshot_sha256=digest,
                    previous_state="failed",
                    next_state="blocked",
                )
                states[node_id] = "blocked"
            if states.get(node_id) != "blocked":
                continue
            failed_dependencies = [
                dep for dep in node["dependencies"] if states.get(dep) == "failed"
            ]
            if failed_dependencies:
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason=(
                        "workflow prerequisite failed: "
                        + ", ".join(sorted(failed_dependencies))
                    ),
                    snapshot_sha256=digest,
                    previous_state="blocked",
                    next_state="failed",
                    details={"failed_dependencies": sorted(failed_dependencies)},
                )
                states[node_id] = "failed"
            elif all(states.get(dep) == "completed" for dep in node["dependencies"]):
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason="all workflow prerequisites completed",
                    snapshot_sha256=digest,
                    previous_state="blocked",
                    next_state="eligible",
                )
                states[node_id] = "eligible"

    def _reconcile_approvals(
        self, snapshot: Mapping[str, Any], status: Mapping[str, Any]
    ) -> None:
        node_map = {str(node["node_id"]): node for node in snapshot["nodes"]}
        status_map = {str(item["node_id"]): item for item in status["nodes"]}
        digest = snapshot_sha256(snapshot)
        for node_id in calculate_eligibility(snapshot, status):
            node = node_map[node_id]
            if node.get("kind", "task") != "approval":
                continue
            subject_id = str(node["approval_for"])
            subject = status_map[subject_id]
            run_id = subject.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason="approval subject has no authoritative child run binding",
                    snapshot_sha256=digest,
                    previous_state="eligible",
                    next_state="failed",
                    details={"approval_for": subject_id},
                )
                continue
            try:
                disposition = lifecycle_disposition(
                    session_run_dir(self.settings, run_id)
                )
            except WorkflowError as exc:
                record_workflow_transition(
                    self.run_dir,
                    workflow_id=str(snapshot["workflow_id"]),
                    node_id=node_id,
                    actor=self.actor,
                    reason=f"approval evidence failed verification: {exc}",
                    snapshot_sha256=digest,
                    previous_state="eligible",
                    next_state="failed",
                    details={"approval_for": subject_id, "subject_run_id": run_id},
                )
                continue
            if disposition is None or disposition["action"] == "reviewed":
                continue
            action = str(disposition["action"])
            details = {
                "approval_for": subject_id,
                "subject_run_id": run_id,
                "approval_action": action,
                "approval_receipt_sha256": disposition["receipt_sha256"],
                "final_receipt_sha256": disposition["final_receipt_sha256"],
                "completion_sha256": disposition["completion_sha256"],
                "revision": disposition["revision"],
            }
            record_workflow_transition(
                self.run_dir,
                workflow_id=str(snapshot["workflow_id"]),
                node_id=node_id,
                actor=self.actor,
                reason=(
                    "canonical lifecycle receipt accepted"
                    if action == "accepted"
                    else "canonical lifecycle receipt rejected"
                ),
                snapshot_sha256=digest,
                previous_state="eligible",
                next_state="completed" if action == "accepted" else "failed",
                details=details,
            )

    def _bind(self, snapshot: Mapping[str, Any], node: Mapping[str, Any], *, retry: bool) -> LaunchPlan:
        status = self.status(snapshot)
        current = next(item for item in status["nodes"] if item["node_id"] == node["node_id"])
        digest = snapshot_sha256(snapshot)
        # A process may have persisted the binding and exited before its
        # running transition. Reuse that binding instead of creating a second
        # launch lineage during replay.
        if (
            not retry
            and current["state"] == "eligible"
            and current["run_id"] is not None
        ):
            return LaunchPlan(
                str(node["node_id"]),
                str(current["run_id"]),
                int(current["attempt"]),
                current["retry_of_run_id"],
            )
        if retry:
            if current["state"] not in {"failed", "recoverable"}:
                raise WorkflowError(f"node {node['node_id']} is not retryable")
            attempt = int(current["attempt"] or 0) + 1
            retry_of = str(current["run_id"])
        else:
            if current["state"] != "eligible":
                raise WorkflowError(f"node {node['node_id']} is not eligible")
            attempt = 1
            retry_of = None
        run_id = self._run_id(str(snapshot["workflow_id"]), node, attempt)
        record_workflow_binding(
            self.run_dir,
            workflow_id=str(snapshot["workflow_id"]),
            node_id=str(node["node_id"]),
            run_id=run_id,
            attempt=attempt,
            retry_of_run_id=retry_of,
            actor=self.actor,
            reason="scheduler launch binding",
            snapshot_sha256=digest,
        )
        if retry:
            record_workflow_transition(
                self.run_dir,
                workflow_id=str(snapshot["workflow_id"]),
                node_id=str(node["node_id"]),
                actor=self.actor,
                reason="retry binding is eligible",
                snapshot_sha256=digest,
                previous_state=str(current["state"]),
                next_state="eligible",
            )
        return LaunchPlan(str(node["node_id"]), run_id, attempt, retry_of)

    def _execute(self, snapshot: Mapping[str, Any], node: Mapping[str, Any], plan: LaunchPlan) -> Any:
        node_with_lineage = dict(node)
        node_with_lineage["pack_id"] = str(node.get("pack_id") or snapshot["pack_id"])
        node_with_lineage["workflow_id"] = str(snapshot["workflow_id"])
        node_with_lineage["workflow_attempt"] = plan.attempt
        node_with_lineage["retry_of_run_id"] = plan.retry_of_run_id
        status = self.status(snapshot)
        try:
            resolved_inputs = resolve_node_inputs(
                snapshot=snapshot,
                status=status,
                node=node,
                settings=self.settings,
                workflow_run_dir=self.run_dir,
                attempt=plan.attempt,
            )
        except WorkflowError as exc:
            record_workflow_transition(
                self.run_dir,
                workflow_id=str(snapshot["workflow_id"]),
                node_id=plan.node_id,
                actor=self.actor,
                reason=f"workflow input binding failed: {exc}",
                snapshot_sha256=snapshot_sha256(snapshot),
                previous_state="eligible",
                next_state="failed",
            )
            raise
        if resolved_inputs is not None:
            node_with_lineage["workflow_inputs"] = resolved_inputs
        if self._child_run_exists(plan.run_id):
            return {"recovered": True, "run_id": plan.run_id}
        try:
            result = self.launch_fn(node_with_lineage, plan.run_id)
        except Exception as exc:
            next_state = "recoverable" if self._child_run_exists(plan.run_id) else "failed"
            record_workflow_transition(
                self.run_dir,
                workflow_id=str(snapshot["workflow_id"]),
                node_id=plan.node_id,
                actor=self.actor,
                reason=f"launch failed; recovery state required: {exc}",
                snapshot_sha256=snapshot_sha256(snapshot),
                previous_state="eligible",
                next_state=next_state,
            )
            raise
        if not self._child_run_exists(plan.run_id):
            record_workflow_transition(
                self.run_dir,
                workflow_id=str(snapshot["workflow_id"]),
                node_id=plan.node_id,
                actor=self.actor,
                reason="launch outcome is not durably authoritative; manual recovery required",
                snapshot_sha256=snapshot_sha256(snapshot),
                previous_state="eligible",
                next_state="recoverable",
            )
            raise WorkflowError(f"launch {plan.run_id} has no authoritative child run")
        record_workflow_transition(
            self.run_dir,
            workflow_id=str(snapshot["workflow_id"]),
            node_id=plan.node_id,
            actor=self.actor,
            reason="authoritative child run exists",
            snapshot_sha256=snapshot_sha256(snapshot),
            previous_state="eligible",
            next_state="running",
            details={
                "child_run_id": plan.run_id,
                "input_binding_sha256": (
                    resolved_inputs["sha256"] if resolved_inputs is not None else None
                ),
            },
        )
        return result

    def launch_eligible(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        with workflow_lock(self.run_dir):
            normalized_status = self.status(snapshot)
            self._reconcile_running(snapshot, normalized_status)
            normalized_status = self.status(snapshot)
            self._reconcile_blocked(snapshot, normalized_status)
            normalized_status = self.status(snapshot)
            self._reconcile_approvals(snapshot, normalized_status)
            normalized_status = self.status(snapshot)
            self._reconcile_blocked(snapshot, normalized_status)
            normalized_status = self.status(snapshot)
            node_map = {str(node["node_id"]): node for node in snapshot["nodes"]}
            node_ids = plan_launches(snapshot, normalized_status, max_parallelism=self.max_parallelism)
            plans = [self._bind(snapshot, node_map[node_id], retry=False) for node_id in node_ids]
            results: dict[str, Any] = {}
            with ThreadPoolExecutor(max_workers=self.max_parallelism) as pool:
                futures: dict[str, Future[Any]] = {
                    plan.node_id: pool.submit(self._execute, snapshot, node_map[plan.node_id], plan)
                    for plan in plans
                }
                for node_id, future in futures.items():
                    results[node_id] = future.result()
            return {"plans": [plan.__dict__ for plan in plans], "results": results}

    def retry(self, snapshot: Mapping[str, Any], node_id: str) -> dict[str, Any]:
        node_id = validate_id(node_id, "workflow node ID")
        node = next((item for item in snapshot["nodes"] if item["node_id"] == node_id), None)
        if node is None:
            raise WorkflowError(f"unknown workflow node: {node_id}")
        if node.get("kind", "task") == "approval":
            raise WorkflowError("approval nodes are evidence gates and cannot be retried")
        with workflow_lock(self.run_dir):
            plan = self._bind(snapshot, node, retry=True)
            return {"plan": plan.__dict__, "result": self._execute(snapshot, node, plan)}

    schedule = launch_eligible


Scheduler = SchedulerService
