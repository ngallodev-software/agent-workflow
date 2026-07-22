from __future__ import annotations

import json
from pathlib import Path

from ..errors import WorkflowError


def write_prediction(
    *,
    instance_id: str,
    model_name_or_path: str,
    patch_path: Path,
    output: Path,
) -> Path:
    if not patch_path.is_file():
        raise WorkflowError(f"patch not found: {patch_path}")
    value = {
        "instance_id": instance_id,
        "model_name_or_path": model_name_or_path,
        "model_patch": patch_path.read_text(encoding="utf-8"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return output
