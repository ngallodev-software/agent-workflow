from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.mcp.server import build_server, main


try:
    import mcp  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    MCP_AVAILABLE = False
else:
    MCP_AVAILABLE = True


class McpOptionalDependencyTests(unittest.TestCase):
    def test_missing_optional_dependency_has_actionable_error(self):
        if MCP_AVAILABLE:
            self.skipTest("MCP extra is installed")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(WorkflowError, "agent-workflow\\[mcp\\]"):
                build_server(defaults(Path(tmp) / "config.toml"), repo_root=Path(tmp))

    def test_main_maps_workflow_error_to_exit_two(self):
        with patch("agent_workflow.mcp.server.build_server", side_effect=WorkflowError("bad")):
            self.assertEqual(main([]), 2)


@unittest.skipUnless(MCP_AVAILABLE, "MCP extra is not installed")
class McpServerProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_facing_registration_uses_public_session_api(self):
        # The official SDK testing guide uses ClientSession over an in-memory
        # transport. Keep this test protocol-facing rather than inspecting
        # FastMCP's private tool/resource managers.
        from mcp.shared.memory import create_connected_server_and_client_session

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = defaults(root / "config.toml")
            settings = settings.__class__(**{**settings.__dict__, "state_root": root / "state"})
            server = build_server(settings, repo_root=Path.cwd())
            async with create_connected_server_and_client_session(server, raise_exceptions=True) as session:
                tools = await session.list_tools()
                resources = await session.list_resources()
                templates = await session.list_resource_templates()
            self.assertEqual([tool.name for tool in tools.tools], ["pack_validate"])
            self.assertIn("agent-workflow://runs", [str(item.uri) for item in resources.resources])
            self.assertEqual(len(templates.resourceTemplates), 3)
