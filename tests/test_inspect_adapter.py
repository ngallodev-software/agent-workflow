import subprocess
import sys
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.inspect_adapter import _load_inspect_api


ROOT = Path(__file__).resolve().parents[1]


class InspectAdapterTests(unittest.TestCase):
    def test_module_import_does_not_import_optional_packages(self):
        code = f"""
import builtins
import sys
sys.path.insert(0, {str(ROOT / 'src')!r})
real_import = builtins.__import__
def deny(name, *args, **kwargs):
    if name.split('.', 1)[0] in {{'inspect_ai', 'inspect_swe'}}:
        raise AssertionError('optional Inspect package imported eagerly')
    return real_import(name, *args, **kwargs)
builtins.__import__ = deny
import agent_workflow.inspect_adapter
"""
        subprocess.run(
            [sys.executable, "-I", "-c", code],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_missing_extra_has_actionable_error(self):
        try:
            _load_inspect_api()
        except WorkflowError as exc:
            self.assertIn("agent-workflow[eval]", str(exc))
