from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_workflow.messages import append_message
from tests.conftest import InstalledProduct
from tests.support import atomic_write_json


def test_installed_stdio_mcp_reads_bounded_metadata_only(
    installed_product: InstalledProduct, product_env: dict[str, str], tmp_path: Path
) -> None:
    if not installed_product.mcp.exists():
        pytest.skip("installed-product fixture did not install the optional MCP extra")
    repo = tmp_path / "repo"
    repo.mkdir()
    state_root = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    run = state_root / "runs" / "mcp-run"
    run.mkdir(parents=True)
    atomic_write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "mcp-run",
            "status": "running",
            "disposition": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "workdir": "/private/workdir",
            "prompt_path": "/private/prompt",
            "log_path": "/private/log",
        },
    )
    secret = "synthetic-secret@example.test"
    append_message(
        run,
        session_id="mcp-run",
        direction="child_to_parent",
        kind="progress",
        actor="child",
        content=secret,
    )

    async def read_resources() -> list[dict[str, object]]:
        server_env = dict(product_env)
        params = StdioServerParameters(
            command=str(installed_product.mcp),
            args=["--repo-root", str(repo)],
            env=server_env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=10)
                responses = [
                    await asyncio.wait_for(session.read_resource("agent-workflow://runs"), timeout=10),
                    await asyncio.wait_for(session.read_resource("agent-workflow://runs/mcp-run/status"), timeout=10),
                    await asyncio.wait_for(session.read_resource("agent-workflow://runs/mcp-run/messages"), timeout=10),
                    await asyncio.wait_for(session.read_resource("agent-workflow://runs/mcp-run/receipts"), timeout=10),
                ]
                return [json.loads(response.contents[0].text) for response in responses]

    responses = asyncio.run(read_resources())
    encoded = json.dumps(responses)
    assert secret not in encoded
    assert all(response.get("schema") for response in responses)
    messages = responses[2]
    item = messages["items"][0]
    assert item["redaction_state"] == "body_omitted"
    assert "content" not in item
    assert responses[0]["items"][0]["session_id"] == "mcp-run"
