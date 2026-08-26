"""Bounded local-stdio MCP adapter for agent-workflow domain services."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..config import Settings, load_settings
from ..errors import WorkflowError
from .services import (
    MCP_CAPABILITIES_URI,
    MCP_COMMAND_CARD_URI,
    MCP_COMMAND_CONTEXT_URI,
    MCP_COMMANDS_URI,
    MCP_MESSAGES_URI,
    MCP_RECEIPTS_URI,
    MCP_ROLE_COMMANDS_URI,
    MCP_RUNS_URI,
    MCP_STATUS_URI,
    PackValidationRequest,
    PageRequest,
    ServiceError,
    WorkflowReadService,
)

_LOGGER = logging.getLogger("agent_workflow.mcp")
_SAFE_ENVIRONMENT = frozenset(
    {
        "HOME", "LANG", "LC_ALL", "LC_CTYPE", "PATH", "TMPDIR",
        "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME",
    }
)


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _repo_root(value: str | None) -> Path:
    candidate = Path(value or Path.cwd())
    return candidate.expanduser()


def _service_result(call: Any) -> Any:
    try:
        return call()
    except ServiceError as exc:
        return exc.as_dict()
    except WorkflowError:
        return ServiceError("request_rejected", "MCP request could not be satisfied").as_dict()
    except Exception:
        correlation_id = str(uuid.uuid4())
        _LOGGER.error("MCP internal failure correlation_id=%s", correlation_id)
        return {
            "schema": "agent-workflow/mcp-error/v1",
            "error": "internal_error",
            "message": "internal MCP failure",
            "correlation_id": correlation_id,
        }


@contextmanager
def _sanitized_environment():
    original = dict(os.environ)
    os.environ.clear()
    os.environ.update({key: value for key, value in original.items() if key in _SAFE_ENVIRONMENT})
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


def build_server(settings: Settings, *, repo_root: Path | None = None) -> Any:
    """Build the FastMCP server using only public SDK imports."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised without extra
        raise WorkflowError(
            "agent-workflow MCP SDK is unavailable; reinstall with the pinned "
            "MCP dependency (for example: pip install 'agent-workflow[mcp]')"
        ) from exc

    service = WorkflowReadService(settings, repository_root=_repo_root(str(repo_root) if repo_root else None))
    instance_id = str(uuid.uuid4())
    server = FastMCP("agent-workflow", json_response=True)

    @server.resource(MCP_CAPABILITIES_URI)
    def capabilities_resource() -> str:
        return _json(_service_result(service.get_capabilities))

    @server.resource(MCP_COMMANDS_URI)
    def commands_resource() -> str:
        return _json(_service_result(service.get_command_catalog))

    @server.resource(MCP_ROLE_COMMANDS_URI)
    def role_commands_resource(role: str) -> str:
        return _json(_service_result(lambda: service.get_command_catalog(role)))

    @server.resource(MCP_RUNS_URI)
    def runs_resource() -> str:
        result = _service_result(lambda: service.list_runs(PageRequest()).as_dict())
        return _json(result)

    @server.resource(MCP_STATUS_URI)
    def status_resource(agent_run_id: str) -> str:
        return _json(_service_result(lambda: service.get_status(agent_run_id)))

    @server.resource(MCP_MESSAGES_URI)
    def messages_resource(agent_run_id: str) -> str:
        result = _service_result(lambda: service.list_messages(agent_run_id, PageRequest()).as_dict())
        return _json(result)

    @server.resource(MCP_RECEIPTS_URI)
    def receipts_resource(agent_run_id: str) -> str:
        result = _service_result(lambda: service.list_receipts(agent_run_id, PageRequest()).as_dict())
        return _json(result)

    @server.resource(MCP_COMMAND_CONTEXT_URI)
    def command_context_resource(agent_run_id: str) -> str:
        return _json(_service_result(lambda: service.get_run_command_context(agent_run_id)))

    @server.resource(MCP_COMMAND_CARD_URI)
    def command_card_resource(agent_run_id: str) -> str:
        return _json(_service_result(lambda: service.get_run_command_card(agent_run_id)))

    @server.tool()
    def pack_validate(pack_root: str) -> dict[str, Any]:
        """Validate one prompt pack under the configured repository root."""
        return _service_result(lambda: service.validate_pack(PackValidationRequest(pack_root)))

    # Public metadata for diagnostics; never used as lifecycle authority.
    server._agent_workflow_actor = f"mcp-stdio:{instance_id}"
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-workflow-mcp")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        server = build_server(settings, repo_root=args.repo_root)
        with _sanitized_environment():
            server.run(transport="stdio")
    except WorkflowError as exc:
        message = str(exc)
        if message.startswith("agent-workflow MCP SDK is unavailable"):
            print(message, file=sys.stderr)
        else:
            print("agent-workflow[mcp]: startup configuration is unavailable", file=sys.stderr)
        return 2
    except Exception:
        correlation_id = str(uuid.uuid4())
        _LOGGER.error("MCP startup failure correlation_id=%s", correlation_id)
        print(f"agent-workflow[mcp]: startup failure; correlation_id={correlation_id}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
