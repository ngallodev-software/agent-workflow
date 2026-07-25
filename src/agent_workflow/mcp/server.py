"""Bounded local-stdio MCP adapter for agent-workflow domain services."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from ..config import Settings, load_settings
from ..errors import WorkflowError
from .services import PackValidationRequest, PageRequest, ServiceError, WorkflowReadService


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def _repo_root(value: str | None) -> Path:
    candidate = Path(value or os.environ.get("AGENT_WORKFLOW_MCP_REPO_ROOT", Path.cwd()))
    return candidate.expanduser().resolve()


def _service_result(call: Any) -> Any:
    try:
        return call()
    except ServiceError as exc:
        return exc.as_dict()


def build_server(settings: Settings, *, repo_root: Path | None = None) -> Any:
    """Build the optional FastMCP server using only public SDK imports."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised without extra
        raise WorkflowError(
            "MCP support requires the optional dependency: "
            "python -m pip install 'agent-workflow[mcp]'"
        ) from exc

    service = WorkflowReadService(settings, repository_root=_repo_root(str(repo_root) if repo_root else None))
    instance_id = str(uuid.uuid4())
    server = FastMCP("agent-workflow", json_response=True)

    @server.resource("agent-workflow://runs")
    def runs_resource() -> str:
        result = _service_result(lambda: service.list_runs(PageRequest()).as_dict())
        return _json(result)

    @server.resource("agent-workflow://runs/{session_id}/status")
    def status_resource(session_id: str) -> str:
        return _json(_service_result(lambda: service.get_status(session_id)))

    @server.resource("agent-workflow://runs/{session_id}/messages")
    def messages_resource(session_id: str) -> str:
        result = _service_result(lambda: service.list_messages(session_id, PageRequest()).as_dict())
        return _json(result)

    @server.resource("agent-workflow://runs/{session_id}/receipts")
    def receipts_resource(session_id: str) -> str:
        result = _service_result(lambda: service.list_receipts(session_id, PageRequest()).as_dict())
        return _json(result)

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
        server = build_server(load_settings(args.config), repo_root=args.repo_root)
        server.run(transport="stdio")
    except WorkflowError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
