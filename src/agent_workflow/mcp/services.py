"""Transport-neutral, bounded read services for the optional MCP adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from ..config import Settings
from ..errors import WorkflowError
from ..manifests import validate_pack
from ..messages import replay_messages
from ..path import absolute_path, inventory_tree, require_directory
from ..state import list_statuses, read_status, run_dir, runs_root
from ..util import validate_id

T = TypeVar("T")
MAX_PAGE_SIZE = 100

_PUBLIC_STATUS_FIELDS = frozenset(
    {
        "schema",
        "session_id",
        "status",
        "disposition",
        "tier",
        "executor",
        "agent_name",
        "agent_class",
        "model",
        "created_at",
        "started_at",
        "finished_at",
        "final_receipt_sha256",
        "failure_category",
    }
)


@dataclass(frozen=True)
class PageRequest:
    after: int = 0
    limit: int = MAX_PAGE_SIZE


@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    next_after: int | None

    def as_dict(self) -> dict[str, Any]:
        return {"items": list(self.items), "next_after": self.next_after}


@dataclass(frozen=True)
class PackValidationRequest:
    pack_root: str


class ServiceError(WorkflowError):
    """Stable service error with a non-secret category."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category

    def as_dict(self) -> dict[str, str]:
        return {"error": self.category, "message": str(self)}


def _page(request: PageRequest, values: list[T]) -> Page[T]:
    if isinstance(request.after, bool) or not isinstance(request.after, int) or request.after < 0:
        raise ServiceError("invalid_cursor", "after must be a non-negative integer")
    if isinstance(request.limit, bool) or not isinstance(request.limit, int):
        raise ServiceError("invalid_limit", "limit must be an integer")
    if request.limit < 1 or request.limit > MAX_PAGE_SIZE:
        raise ServiceError("invalid_limit", f"limit must be between 1 and {MAX_PAGE_SIZE}")
    selected = values[request.after : request.after + request.limit]
    next_after = request.after + len(selected)
    if next_after >= len(values):
        next_after = None
    return Page(tuple(selected), next_after)


def _public_status(value: dict[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in _PUBLIC_STATUS_FIELDS if key in value}


def _validated_run_root(settings: Settings, session_id: str) -> Path:
    try:
        validate_id(session_id, "session ID")
    except WorkflowError as exc:
        raise ServiceError("invalid_identifier", "invalid session identifier") from exc
    try:
        base = require_directory(runs_root(settings), label="configured state run root")
    except WorkflowError as exc:
        raise ServiceError("forbidden_root", "configured state root is unsafe") from exc
    candidate = run_dir(settings, session_id)
    resolved = absolute_path(candidate)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ServiceError("forbidden_root", "run root escapes configured state root") from exc
    try:
        require_directory(resolved, label="run root")
    except WorkflowError as exc:
        raise ServiceError("not_found", "run not found")
    return resolved


def contained_path(root: Path, value: str, label: str) -> Path:
    base = require_directory(root, label="configured repository root")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = absolute_path(candidate)
    if any(part == ".." for part in resolved.parts):
        raise ServiceError("forbidden_root", f"{label} escapes configured root")
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ServiceError("forbidden_root", f"{label} escapes configured root") from exc
    return resolved


class WorkflowReadService:
    def __init__(self, settings: Settings, *, repository_root: Path):
        self.settings = settings
        try:
            self.repository_root = require_directory(repository_root, label="configured repository root")
        except WorkflowError as exc:
            raise ServiceError("invalid_configuration", "configured repository root is not a directory")

    def list_runs(self, request: PageRequest = PageRequest()) -> Page[dict[str, Any]]:
        values = [_public_status(item) for item in list_statuses(self.settings)]
        return _page(request, values)

    def get_status(self, session_id: str) -> dict[str, Any]:
        _validated_run_root(self.settings, session_id)
        try:
            return _public_status(read_status(self.settings, session_id))
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run status is missing or invalid") from exc

    def list_messages(
        self, session_id: str, request: PageRequest = PageRequest()
    ) -> Page[dict[str, Any]]:
        root = _validated_run_root(self.settings, session_id)
        try:
            return _page(request, replay_messages(root))
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run message evidence is invalid") from exc

    def list_receipts(
        self, session_id: str, request: PageRequest = PageRequest()
    ) -> Page[dict[str, str]]:
        root = _validated_run_root(self.settings, session_id)
        receipt_root = root / "receipts"
        try:
            receipt_inventory = inventory_tree(receipt_root)
        except WorkflowError as exc:
            if not receipt_root.exists() and not receipt_root.is_symlink():
                receipt_inventory = ()
            else:
                raise ServiceError("forbidden_root", "receipt tree contains an unsafe entry") from exc
        values: list[dict[str, str]] = []
        for entry in receipt_inventory:
            if entry.kind == "file" and Path(entry.path).match("[0-9]*-*.json"):
                values.append({"name": entry.path, "sha256": str(entry.sha256)})
        return _page(request, values)

    def validate_pack(self, request: PackValidationRequest) -> dict[str, Any]:
        selected = contained_path(self.repository_root, request.pack_root, "pack root")
        if selected.is_symlink():
            raise ServiceError("forbidden_root", "pack root must not be a symlink")
        report = validate_pack(selected).as_dict()
        report["root"] = selected.relative_to(self.repository_root).as_posix() or "."
        return report
