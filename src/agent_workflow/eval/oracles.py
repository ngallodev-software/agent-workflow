from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..errors import WorkflowError
from ..util import sha256_file


@dataclass(frozen=True)
class VerifiedOracle:
    oracle_id: str
    root: Path
    manifest: dict[str, object]
    sha256: str


def resolve_oracle(
    oracle_id: str, expected_sha256: str, oracle_root: Path
) -> VerifiedOracle:
    root = (oracle_root.resolve() / oracle_id).resolve()
    try:
        root.relative_to(oracle_root.resolve())
    except ValueError as exc:
        raise WorkflowError(f"oracle ID escapes oracle root: {oracle_id}") from exc
    path = root / "oracle.json"
    if not path.is_file() or path.is_symlink():
        raise WorkflowError(f"oracle manifest not found or unsafe: {oracle_id}")
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise WorkflowError(
            f"oracle checksum mismatch for {oracle_id}: {digest}; expected {expected_sha256}"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid oracle JSON for {oracle_id}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"oracle manifest must be an object: {oracle_id}")
    return VerifiedOracle(oracle_id, root, value, digest)


def scan_for_leak(canary: bytes, artifact_paths: Iterable[Path]) -> list[str]:
    if not canary:
        raise WorkflowError("oracle canary must not be empty")
    matches: list[str] = []
    for path in artifact_paths:
        if path.is_file() and not path.is_symlink() and canary in path.read_bytes():
            matches.append(str(path))
    return sorted(matches)
