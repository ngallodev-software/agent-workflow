"""Resolve launch prerequisites from immutable evidence through named policies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from .config import Settings
from .errors import WorkflowError
from .lifecycle import lifecycle_receipts
from .protocol_values import PREREQUISITE_REQUIREMENTS
from .receipts import read_sealed_contract, verify_seal_details
from .state import run_dir

PreflightStatus = Literal["accepted", "rejected", "missing", "stale"]
PrerequisiteResolver = Callable[
    [Path, dict[str, Any], str, list[dict[str, Any]], dict[str, Any]],
    dict[str, Any],
]


@dataclass(frozen=True)
class PrerequisitePolicy:
    """One named, deterministic prerequisite evidence policy."""

    name: str
    resolver: PrerequisiteResolver


def _receipt_evidence(
    latest: dict[str, Any], final_digest: str
) -> dict[str, Any]:
    return {
        "receipt_sequence": latest["sequence"],
        "receipt_sha256": latest["sha256"],
        "final_receipt_sha256": final_digest,
    }


def _resolve_accepted_policy(
    _run: Path,
    _final_receipt: dict[str, Any],
    final_digest: str,
    receipts: list[dict[str, Any]],
    base: dict[str, Any],
) -> dict[str, Any]:
    if not receipts:
        return {
            **base,
            "status": "missing",
            "reason": f"prerequisite has no lifecycle receipts: {base['agent_run_id']}",
        }
    latest = receipts[-1]
    action = latest["receipt"].get("action")
    evidence = _receipt_evidence(latest, final_digest)
    outcomes: dict[str, tuple[str, str]] = {
        "accepted": ("accepted", "prerequisite accepted in current lifecycle receipt"),
        "rejected": (
            "rejected",
            f"prerequisite rejected: {latest['receipt'].get('reason', 'no reason provided')}",
        ),
        "reviewed": ("rejected", "prerequisite reviewed but not accepted"),
    }
    status, reason = outcomes.get(
        str(action), ("rejected", f"unsupported prerequisite lifecycle action: {action!r}")
    )
    return {**base, "status": status, "reason": reason, **evidence}


def _resolve_sealed_completed_policy(
    run: Path,
    final_receipt: dict[str, Any],
    final_digest: str,
    receipts: list[dict[str, Any]],
    base: dict[str, Any],
) -> dict[str, Any]:
    try:
        final_status, _ = read_sealed_contract(
            run,
            final_receipt,
            "final-status.json",
            "agent-workflow/agent-run-status/v1",
        )
        completion, _ = read_sealed_contract(
            run,
            final_receipt,
            "completion.json",
            "agent-workflow/completion/v1",
        )
        collection, _ = read_sealed_contract(
            run,
            final_receipt,
            "collections/completion.json",
            "agent-workflow/completion-collection/v1",
        )
    except WorkflowError as exc:
        return {
            **base,
            "status": "stale",
            "reason": f"prerequisite sealed completion evidence is stale: {exc}",
        }

    gates = (
        final_status.get("status") == "completed",
        completion.get("result") == "completed",
        collection.get("validation_status") == "valid",
    )
    if not all(gates):
        return {
            **base,
            "status": "rejected",
            "reason": "prerequisite is sealed but not successfully completed",
            "final_receipt_sha256": final_digest,
        }

    latest = receipts[-1] if receipts else None
    if latest is not None and latest["receipt"].get("action") == "rejected":
        return {
            **base,
            "status": "rejected",
            "reason": f"prerequisite rejected: {latest['receipt'].get('reason', 'no reason provided')}",
            **_receipt_evidence(latest, final_digest),
        }

    evidence: dict[str, Any] = {"final_receipt_sha256": final_digest}
    if latest is not None:
        evidence.update(_receipt_evidence(latest, final_digest))
    return {
        **base,
        "status": "accepted",
        "reason": "prerequisite has verified sealed-completed evidence and is reviewable",
        **evidence,
    }


_PREREQUISITE_POLICIES: dict[str, PrerequisitePolicy] = {
    "accepted": PrerequisitePolicy("accepted", _resolve_accepted_policy),
    "sealed_completed": PrerequisitePolicy(
        "sealed_completed", _resolve_sealed_completed_policy
    ),
}


def prerequisite_policy(requirement: str) -> PrerequisitePolicy:
    if requirement not in PREREQUISITE_REQUIREMENTS:
        raise WorkflowError(
            "prerequisite requirement must be one of: "
            + ", ".join(PREREQUISITE_REQUIREMENTS)
        )
    return _PREREQUISITE_POLICIES[requirement]


def resolve_prerequisites(
    settings: Settings,
    prerequisite_ids: list[str],
    *,
    requirement: str = "accepted",
) -> dict[str, Any]:
    """Resolve prerequisites through one named immutable-evidence policy."""
    policy = prerequisite_policy(requirement)
    if not prerequisite_ids:
        return {
            "schema": "agent-workflow/preflight/v1",
            "status": "accepted",
            "reason": "no prerequisites required",
            "requirement": policy.name,
            "prerequisites": [],
        }
    results = [
        _resolve_single(settings, agent_run_id, policy=policy)
        for agent_run_id in prerequisite_ids
    ]
    statuses = {item["status"] for item in results}
    if statuses == {"accepted"}:
        status: PreflightStatus = "accepted"
        reason = "all prerequisites accepted"
    else:
        precedence = ("stale", "missing", "rejected")
        status = next(
            candidate for candidate in precedence if candidate in statuses
        )  # type: ignore[assignment]
        reason = "; ".join(
            item["reason"] for item in results if item["status"] == status
        )
    return {
        "schema": "agent-workflow/preflight/v1",
        "status": status,
        "reason": reason,
        "requirement": policy.name,
        "prerequisites": results,
    }


def _resolve_single(
    settings: Settings,
    agent_run_id: str,
    *,
    policy: PrerequisitePolicy,
) -> dict[str, Any]:
    run = run_dir(settings, agent_run_id)
    base = {"agent_run_id": agent_run_id}
    if not run.exists():
        return {
            **base,
            "status": "missing",
            "reason": f"prerequisite Agent Run not found: {agent_run_id}",
        }
    if not (run / "final-receipt.json").exists():
        return {
            **base,
            "status": "missing",
            "reason": f"prerequisite has no sealed final receipt: {agent_run_id}",
        }
    try:
        final_receipt, final_digest = verify_seal_details(run)
        receipts = lifecycle_receipts(
            run, expected_final_receipt_sha256=final_digest
        )
    except WorkflowError as exc:
        return {
            **base,
            "status": "stale",
            "reason": f"prerequisite immutable evidence is stale: {exc}",
        }
    return policy.resolver(run, final_receipt, final_digest, receipts, base)


def preflight_error(preflight: dict[str, Any]) -> WorkflowError:
    return WorkflowError(
        f"Agent Run preflight failed ({preflight.get('status')} prerequisites): "
        f"{preflight.get('reason')}"
    )


def preflight_run_record(
    *,
    agent_run_id: str,
    ticket_id: str | None,
    pack_id: str | None,
    workdir: Path,
    prompt_path: Path,
    log_path: Path,
    preflight: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Return a schema-valid failed status for a rejected preparation attempt."""
    return {
        "schema": "agent-workflow/agent-run-status/v1",
        "agent_run_id": agent_run_id,
        "ticket_id": ticket_id,
        "pack_id": pack_id,
        "status": "failed",
        "failure_category": "preflight_failed",
        "preflight": preflight,
        "disposition": None,
        "created_at": created_at,
        "updated_at": created_at,
        "workdir": str(workdir),
        "prompt_path": str(prompt_path),
        "prompt_source": str(prompt_path),
        "log_path": str(log_path),
        "worker_mode": "headless",
        "worker_id": None,
        "worker_pid": None,
        "worker_process_group_id": None,
        "worker_alive": None,
        "final_receipt_path": None,
    }
