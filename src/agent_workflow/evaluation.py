from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import read_contract
from .errors import WorkflowError

EVALUATION_SCHEMA = "agent-workflow/evaluation-plan/v1"


@dataclass(frozen=True)
class EvaluationPlan:
    path: Path
    data: dict[str, Any]
    sha256: str

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.data["task_ids"])


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_evaluation(
    path: Path,
    *,
    pack_root: Path | None = None,
    task_ids: set[str] | None = None,
) -> EvaluationPlan:
    path = path.expanduser().resolve()
    if pack_root is not None:
        pack_root = pack_root.expanduser().resolve()
        try:
            path.relative_to(pack_root)
        except ValueError as exc:
            raise WorkflowError(f"evaluation plan escapes pack root: {path}") from exc
    data = read_contract(path, EVALUATION_SCHEMA)
    declared = {str(item) for item in data["task_ids"]}
    if task_ids is not None:
        unknown = sorted(declared - task_ids)
        if unknown:
            raise WorkflowError(f"evaluation plan references unknown tasks: {unknown}")
    oracle_refs = data.get("oracle_refs", {})
    if set(oracle_refs) - declared:
        raise WorkflowError(
            "evaluation oracle_refs must reference declared task_ids: "
            f"{sorted(set(oracle_refs) - declared)}"
        )
    return EvaluationPlan(path=path, data=data, sha256=canonical_json_sha256(data))
