"""Transport-neutral, bounded read services for the optional MCP adapter."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from ..config import Settings
from ..errors import WorkflowError
from ..lifecycle import lifecycle_receipts
from ..manifests import validate_pack
from ..messages import replay_messages_descriptor
from ..path_security import open_beneath, open_relative, validate_contained, validate_directory
from ..state import _current
from ..util import validate_id

T = TypeVar("T")

PAGE_SCHEMA = "agent-workflow/mcp-page/v1"
ERROR_SCHEMA = "agent-workflow/mcp-error/v1"
MAX_PAGE_SIZE = 100
MAX_CURSOR = 1_000_000
MAX_TEXT_CHARS = 512
MAX_STATUS_BYTES = 256 * 1024

_PUBLIC_STATUS_FIELDS = (
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
        return {
            "schema": PAGE_SCHEMA,
            "items": list(self.items),
            "count": len(self.items),
            "next_after": self.next_after,
        }


@dataclass(frozen=True)
class PackValidationRequest:
    pack_root: str


class ServiceError(WorkflowError):
    """Stable service error with a non-secret category."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category

    def as_dict(self) -> dict[str, str]:
        return {"schema": ERROR_SCHEMA, "error": self.category, "message": str(self)}


def _page(request: PageRequest, values: list[T]) -> Page[T]:
    if isinstance(request.after, bool) or not isinstance(request.after, int) or request.after < 0:
        raise ServiceError("invalid_cursor", "after must be a non-negative integer")
    if request.after > MAX_CURSOR:
        raise ServiceError("invalid_cursor", f"after must not exceed {MAX_CURSOR}")
    if isinstance(request.limit, bool) or not isinstance(request.limit, int):
        raise ServiceError("invalid_limit", "limit must be an integer")
    if request.limit < 1 or request.limit > MAX_PAGE_SIZE:
        raise ServiceError("invalid_limit", f"limit must be between 1 and {MAX_PAGE_SIZE}")
    selected = values[request.after : request.after + request.limit]
    next_after = request.after + len(selected)
    if next_after >= len(values):
        next_after = None
    return Page(tuple(selected), next_after)


def _bounded_text(value: Any, *, label: str) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
        raise ServiceError("invalid_evidence", f"{label} exceeds the MCP text limit")
    return value


def _public_status(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ServiceError("invalid_evidence", "run status is invalid")
    result: dict[str, Any] = {}
    for key in _PUBLIC_STATUS_FIELDS:
        if key in value:
            result[key] = _bounded_text(value[key], label=f"status {key}")
    if not isinstance(result.get("session_id"), str) or not isinstance(result.get("status"), str):
        raise ServiceError("invalid_evidence", "run status is missing required metadata")
    return result


def _read_fd(fd: int, *, maximum: int) -> bytes:
    with os.fdopen(os.dup(fd), "rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ServiceError("output_limit", "evidence exceeds the MCP output limit")
    return data


def _read_json_fd(fd: int) -> Any:
    try:
        return json.loads(_read_fd(fd, maximum=MAX_STATUS_BYTES).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ServiceError("invalid_evidence", "run status is invalid JSON") from exc


def _path_error(exc: BaseException, *, missing: str, unsafe: str) -> ServiceError:
    if isinstance(exc, WorkflowError) and "does not exist" in str(exc):
        return ServiceError("not_found", missing)
    if isinstance(exc, OSError) and exc.errno == errno.ENOENT:
        return ServiceError("not_found", missing)
    return ServiceError("forbidden_root", unsafe)


def _message_metadata(message: dict[str, Any]) -> dict[str, Any]:
    content = message["content"].encode("utf-8")
    kind = message["kind"]
    return {
        "schema": "agent-workflow/session-message-metadata/v1",
        "sequence": message["sequence"],
        "message_id": message["message_id"],
        "session_id": message["session_id"],
        "timestamp": _bounded_text(message["timestamp"], label="message timestamp"),
        "type": kind,
        "direction": message["direction"],
        "actor": "local-mcp",
        "principal": "local-mcp",
        "correlation_id": message.get("correlation_id"),
        "disposition": "acknowledged" if kind == "ack" else ("pending" if kind == "steer" else None),
        "content_length": len(content),
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "redaction_state": "body_omitted",
    }


def contained_path(root: Path, value: str, label: str) -> Path:
    try:
        return validate_contained(root, value, label=label)
    except WorkflowError as exc:
        if "escapes" in str(exc) or "unsafe" in str(exc) or "traversal" in str(exc):
            raise ServiceError("forbidden_root", f"{label} is outside the configured root") from exc
        raise ServiceError("not_found", f"{label} is unavailable") from exc


class WorkflowReadService:
    def __init__(self, settings: Settings, *, repository_root: Path):
        self.settings = settings
        try:
            self.repository_root = validate_directory(repository_root, label="repository root")
            validate_directory(settings.state_root, label="state root")
        except (OSError, WorkflowError) as exc:
            raise ServiceError("invalid_configuration", "configured MCP roots are invalid") from exc

    def _runs_fd(self) -> int | None:
        try:
            return open_beneath(
                self.settings.state_root,
                "runs",
                flags=os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                return None
            raise ServiceError("forbidden_root", "configured state root is unsafe") from exc
        except WorkflowError as exc:
            raise ServiceError("forbidden_root", "configured state root is unsafe") from exc

    def _status_from_runs_fd(self, runs_fd: int, session_id: str) -> dict[str, Any]:
        try:
            run_fd = open_relative(
                runs_fd,
                session_id,
                flags=os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                status_fd = open_relative(run_fd, "status.json", flags=os.O_RDONLY)
            finally:
                os.close(run_fd)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                raise ServiceError("not_found", "run not found") from exc
            raise ServiceError("forbidden_root", "run evidence path is unsafe") from exc
        try:
            value = _current(_read_json_fd(status_fd))
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run status is missing or invalid") from exc
        finally:
            os.close(status_fd)
        if value.get("session_id") != session_id:
            raise ServiceError("invalid_evidence", "run status identity is invalid")
        return _public_status(value)

    def list_runs(self, request: PageRequest = PageRequest()) -> Page[dict[str, Any]]:
        runs_fd = self._runs_fd()
        if runs_fd is None:
            return _page(request, [])
        try:
            values: list[dict[str, Any]] = []
            for name in sorted(os.listdir(runs_fd)):
                try:
                    validate_id(name, "session ID")
                except WorkflowError:
                    raise ServiceError("invalid_evidence", "run directory identity is invalid")
                values.append(self._status_from_runs_fd(runs_fd, name))
            return _page(request, values)
        finally:
            os.close(runs_fd)

    def _validated_run_root(self, session_id: str) -> Path:
        try:
            validate_id(session_id, "session ID")
        except WorkflowError as exc:
            raise ServiceError("invalid_identifier", "invalid session identifier") from exc
        try:
            return validate_contained(self.settings.state_root, Path("runs") / session_id, label="run root")
        except (OSError, WorkflowError) as exc:
            raise _path_error(exc, missing="run not found", unsafe="run root is unsafe") from exc

    def get_status(self, session_id: str) -> dict[str, Any]:
        runs_fd = self._runs_fd()
        if runs_fd is None:
            raise ServiceError("not_found", "run not found")
        try:
            validate_id(session_id, "session ID")
        except WorkflowError as exc:
            os.close(runs_fd)
            raise ServiceError("invalid_identifier", "invalid session identifier") from exc
        try:
            return self._status_from_runs_fd(runs_fd, session_id)
        finally:
            os.close(runs_fd)

    def list_messages(
        self, session_id: str, request: PageRequest = PageRequest()
    ) -> Page[dict[str, Any]]:
        root = self._validated_run_root(session_id)
        try:
            descriptor = open_beneath(root, "messages.jsonl", flags=os.O_RDONLY)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                return _page(request, [])
            raise ServiceError("forbidden_root", "message evidence path is unsafe") from exc
        except WorkflowError as exc:
            raise ServiceError("forbidden_root", "message evidence path is unsafe") from exc
        try:
            messages = replay_messages_descriptor(descriptor)
            return _page(request, [_message_metadata(message) for message in messages])
        except ServiceError:
            raise
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run message evidence is invalid") from exc
        finally:
            os.close(descriptor)

    def list_receipts(
        self, session_id: str, request: PageRequest = PageRequest()
    ) -> Page[dict[str, Any]]:
        root = self._validated_run_root(session_id)
        try:
            chain = lifecycle_receipts(root)
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run receipt evidence is invalid") from exc
        values: list[dict[str, Any]] = []
        for entry in chain:
            receipt = entry["receipt"]
            values.append(
                {
                    "schema": "agent-workflow/lifecycle-receipt-summary/v1",
                    "sequence": entry["sequence"],
                    "action": receipt["action"],
                    "created_at": _bounded_text(receipt["created_at"], label="receipt timestamp"),
                    "final_receipt_sha256": receipt["final_receipt_sha256"],
                    "score_receipt_sha256": receipt.get("score_receipt_sha256"),
                    "reviewer_independent": receipt.get("reviewer_independent"),
                    "sha256": entry["sha256"],
                }
            )
        return _page(request, values)

    def validate_pack(self, request: PackValidationRequest) -> dict[str, Any]:
        selected = contained_path(self.repository_root, request.pack_root, "pack root")
        try:
            report = validate_pack(selected).as_dict()
        except WorkflowError as exc:
            raise ServiceError("invalid_pack", "prompt pack validation failed") from exc
        result: dict[str, Any] = {
            "schema": "agent-workflow/mcp-pack-validation/v1",
            "root": ".",
            "ok": report["ok"],
            "phase_count": report["phase_count"],
            "task_count": report["task_count"],
            "errors": ["pack_validation_failed"] if report["errors"] else [],
            "warnings": ["pack_validation_warning"] if report["warnings"] else [],
        }
        try:
            descriptor = open_beneath(selected, "MANIFEST.sha256", flags=os.O_RDONLY)
        except OSError:
            descriptor = None
        if descriptor is not None:
            try:
                result["manifest_sha256"] = hashlib.sha256(_read_fd(descriptor, maximum=MAX_STATUS_BYTES)).hexdigest()
            finally:
                os.close(descriptor)
        return result
