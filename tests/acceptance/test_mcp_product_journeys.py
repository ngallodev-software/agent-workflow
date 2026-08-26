from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("mcp", reason="install the optional mcp feature to run MCP acceptance")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_workflow.messages import append_message
from tests.conftest import (
    prepare_and_start_agent_run,
    InstalledProduct,
    fake_agent_path,
    git_repo,
    wait_for_status,
)


def test_installed_stdio_mcp_reads_bounded_metadata_only(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    if not installed_product.mcp_sdk_available:
        pytest.skip("installed-product fixture does not have the optional mcp feature")
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Complete the bounded MCP launch journey.\n", encoding="utf-8")
    prepare_and_start_agent_run(
        installed_product,
        "mcp-run",
        repo,
        prompt,
        "--tier",
        "low",
        "--no-interactive",
        "--",
        fake_agent_path,
        env=product_env,
    )
    wait_for_status(product_env, "mcp-run")

    state_root = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    run = state_root / "runs" / "mcp-run"
    secret = "synthetic-secret@example.test"
    append_message(
        run,
        agent_run_id="mcp-run",
        direction="child_to_parent",
        kind="progress",
        actor="child",
        content=secret,
    )

    async def read_resources(*uris: str) -> list[dict[str, object]]:
        params = StdioServerParameters(
            command=str(installed_product.mcp),
            args=["--repo-root", str(repo)],
            env=dict(product_env),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=10)
                responses = [
                    await asyncio.wait_for(session.read_resource(uri), timeout=10)
                    for uri in uris
                ]
                return [json.loads(response.contents[0].text) for response in responses]

    responses = asyncio.run(
        read_resources(
            "agent-workflow://capabilities",
            "agent-workflow://commands/implementation",
            "agent-workflow://commands/unknown",
            "agent-workflow://runs",
            "agent-workflow://runs/mcp-run/status",
            "agent-workflow://runs/mcp-run/messages",
            "agent-workflow://runs/mcp-run/receipts",
            "agent-workflow://runs/mcp-run/command-context",
            "agent-workflow://runs/mcp-run/command-card",
        )
    )
    encoded = json.dumps(responses)
    assert secret not in encoded
    assert str(repo) not in encoded
    assert all(response.get("schema") for response in responses)

    capabilities, commands, unknown_commands, runs, _, messages, _, context, card = responses
    assert capabilities["mode"] == "read-only"
    assert capabilities["command_catalog"]["leaf_command_count"] >= len(commands["commands"])
    represented = {item["command"] for item in commands["commands"]}
    assert {"progress", "ack", "agent task-complete"} <= represented
    assert "worktree create" not in represented
    assert unknown_commands["schema"] == "agent-workflow/mcp-error/v1"
    assert unknown_commands["error"] == "invalid_identifier"
    assert context["verification"] == "verified"
    assert context["role"] == "implementation"
    assert context["catalog_sha256"] == capabilities["command_catalog"]["sha256"]
    assert context["cli_invocation"] == ["agent-workflow"]
    assert card["sha256"] == context["card_sha256"]
    assert "Do not run `--help`" in card["markdown"]
    assert "agent-workflow progress" in card["markdown"]
    assert "agent-workflow worktree create" not in card["markdown"]
    item = messages["items"][0]
    assert item["redaction_state"] == "body_omitted"
    assert item["content_length"] == len(secret.encode())
    assert "content" not in item
    assert runs["items"][0]["agent_run_id"] == "mcp-run"

    card_path = run / "command-card.md"
    card_path.chmod(0o644)
    card_path.write_text(card_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    os.chmod(card_path, 0o444)
    tampered = asyncio.run(
        read_resources("agent-workflow://runs/mcp-run/command-context")
    )[0]
    assert tampered["schema"] == "agent-workflow/mcp-error/v1"
    assert tampered["error"] == "invalid_evidence"
