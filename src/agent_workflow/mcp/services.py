"""Transport-neutral, bounded read services for the optional MCP adapter."""

from __future__ import annotations

import errno
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, TypeVar

from .. import __version__
from ..command_catalog import (
    COMMAND_CATALOG_SCHEMA,
    COMMAND_ROLES,
    command_catalog_sha256,
    filter_catalog,
    runtime_command_catalog,
)
from ..config import Settings
from ..contracts import read_agent_run_contract, validate_instance
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
MAX_COMMAND_CARD_BYTES = 256 * 1024

MCP_CAPABILITIES_URI = "agent-workflow://capabilities"
MCP_COMMANDS_URI = "agent-workflow://commands"
MCP_ROLE_COMMANDS_URI = "agent-workflow://commands/{role}"
MCP_RUNS_URI = "agent-workflow://runs"
MCP_STATUS_URI = "agent-workflow://runs/{agent_run_id}/status"
MCP_MESSAGES_URI = "agent-workflow://runs/{agent_run_id}/messages"
MCP_RECEIPTS_URI = "agent-workflow://runs/{agent_run_id}/receipts"
MCP_COMMAND_CONTEXT_URI = "agent-workflow://runs/{agent_run_id}/command-context"
MCP_COMMAND_CARD_URI = "agent-workflow://runs/{agent_run_id}/command-card"
MCP_RESOURCE_URIS = (
    MCP_CAPABILITIES_URI,
    MCP_COMMANDS_URI,
    MCP_ROLE_COMMANDS_URI,
    MCP_RUNS_URI,
    MCP_STATUS_URI,
    MCP_MESSAGES_URI,
    MCP_RECEIPTS_URI,
    MCP_COMMAND_CONTEXT_URI,
    MCP_COMMAND_CARD_URI,
)
MCP_TOOL_NAMES = ("pack_validate",)
MCP_EXCLUDED_OPERATIONS = (
    "arbitrary-shell",
    "direct-state-mutation",
    "force-kill",
    "network-transport",
    "raw-terminal-capture",
)

_PUBLIC_STATUS_FIELDS = (
    "schema",
    "agent_run_id",
    "status",
    "disposition",
    "tier",
    "agent_name",
    "role",
    "role_digest",
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
    if (
        isinstance(request.after, bool)
        or not isinstance(request.after, int)
        or request.after < 0
    ):
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
    if not isinstance(result.get("agent_run_id"), str) or not isinstance(result.get("status"), str):
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
        "schema": "agent-workflow/agent-run-message-metadata/v1",
        "sequence": message["sequence"],
        "message_id": message["message_id"],
        "agent_run_id": message["agent_run_id"],
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


def _public_cli_invocation(value: Any) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ServiceError("invalid_evidence", "launch CLI invocation is invalid")
    # Preserve the executable identity without disclosing an installation path.
    executable = Path(value[0]).name
    if not executable:
        raise ServiceError("invalid_evidence", "launch CLI invocation is invalid")
    return [executable, *value[1:]]


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

    def _status_from_runs_fd(self, runs_fd: int, agent_run_id: str) -> dict[str, Any]:
        try:
            run_fd = open_relative(
                runs_fd,
                agent_run_id,
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
        if value.get("agent_run_id") != agent_run_id:
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
                    validate_id(name, "agent run ID")
                except WorkflowError:
                    raise ServiceError("invalid_evidence", "run directory identity is invalid")
                values.append(self._status_from_runs_fd(runs_fd, name))
            return _page(request, values)
        finally:
            os.close(runs_fd)

    def _validated_run_root(self, agent_run_id: str) -> Path:
        try:
            validate_id(agent_run_id, "agent run ID")
        except WorkflowError as exc:
            raise ServiceError("invalid_identifier", "invalid Agent Run identifier") from exc
        try:
            return validate_contained(self.settings.state_root, Path("runs") / agent_run_id, label="run root")
        except (OSError, WorkflowError) as exc:
            raise _path_error(exc, missing="run not found", unsafe="run root is unsafe") from exc

    def get_status(self, agent_run_id: str) -> dict[str, Any]:
        runs_fd = self._runs_fd()
        if runs_fd is None:
            raise ServiceError("not_found", "run not found")
        try:
            validate_id(agent_run_id, "agent run ID")
        except WorkflowError as exc:
            os.close(runs_fd)
            raise ServiceError("invalid_identifier", "invalid Agent Run identifier") from exc
        try:
            return self._status_from_runs_fd(runs_fd, agent_run_id)
        finally:
            os.close(runs_fd)

    def list_messages(
        self, agent_run_id: str, request: PageRequest = PageRequest()
    ) -> Page[dict[str, Any]]:
        root = self._validated_run_root(agent_run_id)
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
        self, agent_run_id: str, request: PageRequest = PageRequest()
    ) -> Page[dict[str, Any]]:
        root = self._validated_run_root(agent_run_id)
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

    def get_command_catalog(self, role: str | None = None) -> dict[str, Any]:
        if role is not None and role not in COMMAND_ROLES:
            raise ServiceError("invalid_identifier", "unknown command-catalog role")
        try:
            catalog = filter_catalog(runtime_command_catalog(self.settings), role)
            validate_instance(
                catalog, COMMAND_CATALOG_SCHEMA, artifact="MCP command catalog"
            )
        except WorkflowError as exc:
            raise ServiceError(
                "invalid_evidence", "installed command catalog is invalid"
            ) from exc
        return catalog

    def get_capabilities(self) -> dict[str, Any]:
        catalog = self.get_command_catalog()
        result = {
            "schema": "agent-workflow/mcp-capabilities/v1",
            "application_version": __version__,
            "transport": "stdio",
            "mode": "read-only",
            "command_catalog": {
                "schema": COMMAND_CATALOG_SCHEMA,
                "sha256": command_catalog_sha256(catalog),
                "leaf_command_count": len(catalog["commands"]),
            },
            "launch_contracts": [
                "agent-workflow/agent-run-contract/v1",
                "agent-workflow/agent-run-contract/v1",
            ],
            "resources": list(MCP_RESOURCE_URIS),
            "tools": list(MCP_TOOL_NAMES),
            "excluded_operations": list(MCP_EXCLUDED_OPERATIONS),
        }
        try:
            validate_instance(
                result,
                "agent-workflow/mcp-capabilities/v1",
                artifact="MCP capabilities",
            )
        except WorkflowError as exc:
            raise ServiceError(
                "invalid_evidence", "installed MCP capabilities are invalid"
            ) from exc
        return result

    def _launch_contract(self, agent_run_id: str) -> tuple[Path, dict[str, Any]]:
        root = self._validated_run_root(agent_run_id)
        try:
            descriptor = open_beneath(root, "agent-run-contract.json", flags=os.O_RDONLY)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                raise ServiceError("not_found", "run launch contract not found") from exc
            raise ServiceError(
                "forbidden_root", "run launch contract path is unsafe"
            ) from exc
        except WorkflowError as exc:
            raise ServiceError(
                "forbidden_root", "run launch contract path is unsafe"
            ) from exc
        else:
            os.close(descriptor)
        try:
            contract = read_agent_run_contract(root / "agent-run-contract.json")
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run launch contract is invalid") from exc
        if contract.get("agent_run", {}).get("id") != agent_run_id:
            raise ServiceError(
                "invalid_evidence", "run launch contract identity is invalid"
            )
        return root, contract

    def get_run_command_context(self, agent_run_id: str) -> dict[str, Any]:
        _, contract = self._launch_contract(agent_run_id)
        launch_schema = contract["schema"]
        binding = contract.get("command_catalog")
        if not isinstance(binding, dict):
            raise ServiceError("invalid_evidence", "run command binding is invalid")
        result = {
            "schema": "agent-workflow/mcp-run-command-context/v1",
            "agent_run_id": agent_run_id,
            "launch_contract_schema": launch_schema,
            "verification": "verified",
            "role": binding.get("role"),
            "catalog_schema": binding.get("catalog_schema"),
            "catalog_sha256": binding.get("catalog_sha256"),
            "card_sha256": binding.get("card_sha256"),
            "cli_invocation": _public_cli_invocation(binding.get("cli_invocation")),
        }
        try:
            validate_instance(
                result,
                "agent-workflow/mcp-run-command-context/v1",
                artifact="MCP run command context",
            )
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run command context is invalid") from exc
        return result

    def get_run_command_card(self, agent_run_id: str) -> dict[str, Any]:
        root, contract = self._launch_contract(agent_run_id)
        binding = contract["command_catalog"]
        card_name = binding["card_path"]
        try:
            descriptor = open_beneath(root, card_name, flags=os.O_RDONLY)
        except (OSError, WorkflowError) as exc:
            raise ServiceError("invalid_evidence", "run command card is unavailable") from exc
        try:
            card = _read_fd(descriptor, maximum=MAX_COMMAND_CARD_BYTES)
        finally:
            os.close(descriptor)
        digest = hashlib.sha256(card).hexdigest()
        if digest != binding["card_sha256"]:
            raise ServiceError("invalid_evidence", "run command card digest is invalid")
        try:
            markdown = card.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ServiceError("invalid_evidence", "run command card is not UTF-8") from exc
        result = {
            "schema": "agent-workflow/mcp-run-command-card/v1",
            "agent_run_id": agent_run_id,
            "role": binding["role"],
            "sha256": digest,
            "markdown": markdown,
        }
        try:
            validate_instance(
                result,
                "agent-workflow/mcp-run-command-card/v1",
                artifact="MCP run command card",
            )
        except WorkflowError as exc:
            raise ServiceError("invalid_evidence", "run command card is invalid") from exc
        return result

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
