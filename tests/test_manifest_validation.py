import tempfile
import unittest
from pathlib import Path

from agent_workflow.manifests import validate_pack, write_checksum_manifest


class ManifestValidationTests(unittest.TestCase):
    def test_example_pack_validates_with_generated_checksums(self):
        root = Path(__file__).resolve().parents[1] / "examples" / "three-phase-pack"
        write_checksum_manifest(root)
        report = validate_pack(root)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(report.phases, 3)
        self.assertEqual(report.tasks, 3)

    def test_missing_ticket_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required = [
                "README.md",
                "EXECUTION_PROTOCOL.md",
                "DELEGATION_RUNBOOK.md",
                "templates/TICKET_COMPLETION.md",
                "templates/PHASE_GATE_REPORT.md",
                "templates/source-baseline.example.json",
                "phase-0/README.md",
                "phase-0/MASTER_IMPLEMENTATION_PROMPT.md",
            ]
            for rel in required:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder\n", encoding="utf-8")
            (root / "phase-0/tickets").mkdir()
            (root / "phase-0/task-manifest.yaml").write_text(
                "phase: 0\nname: test\ntasks:\n"
                "  - {id: P0-00, tier: C, session: test-p0-00, "
                "prompt: tickets/missing.md}\n",
                encoding="utf-8",
            )
            report = validate_pack(root, verify_checksums=False)
            self.assertFalse(report.ok)
            self.assertTrue(
                any("prompt not found" in error for error in report.errors)
            )

class MiniYamlFallbackTests(unittest.TestCase):
    def test_builtin_parser_handles_block_and_inline_tasks(self):
        from agent_workflow.miniyaml import load_task_manifest

        block = load_task_manifest(
            "phase: 0\nname: test\nmandatory_order: [P0-00]\n"
            "tasks:\n  - id: P0-00\n    tier: C\n"
            "    session: test-p0-00\n    prompt: tickets/P0-00.md\n"
        )
        inline = load_task_manifest(
            "phase: 0\nname: test\ntasks:\n"
            "  - {id: P0-00, tier: C, session: test-p0-00, "
            "prompt: tickets/P0-00.md}\n"
        )
        self.assertEqual(block["tasks"][0]["session"], "test-p0-00")
        self.assertEqual(inline["tasks"][0]["tier"], "C")
