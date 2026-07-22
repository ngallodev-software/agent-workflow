from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .errors import WorkflowError

Migration = Callable[[Mapping[str, Any]], dict[str, Any]]


def _status_v1_to_v2(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    old_status = str(result.get("status", ""))
    disposition = None
    if old_status in {"accepted", "rejected"}:
        disposition = old_status
        result["status"] = "completed"
    result["schema"] = "agent-workflow/session-status/v2"
    result.setdefault("disposition", disposition)
    result.setdefault("final_receipt_path", None)
    result.setdefault("failure_category", None)
    return result


_MIGRATIONS: dict[tuple[str, str], Migration] = {
    (
        "agent-workflow/session-status/v1",
        "agent-workflow/session-status/v2",
    ): _status_v1_to_v2,
}


def migrate_contract(value: Mapping[str, Any], target_schema: str) -> dict[str, Any]:
    source = value.get("schema")
    if source == target_schema:
        return dict(value)
    if not isinstance(source, str):
        raise WorkflowError("contract missing string schema")
    migration = _MIGRATIONS.get((source, target_schema))
    if migration is None:
        raise WorkflowError(f"no contract migration: {source} -> {target_schema}")
    return migration(value)
