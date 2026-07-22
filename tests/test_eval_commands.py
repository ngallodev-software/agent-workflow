import tempfile
import unittest
from pathlib import Path

from agent_workflow.eval.commands import CommandSpec, collect_commands
from agent_workflow.eval.junit import compare_junit, parse_junit


class CommandCollectorTests(unittest.TestCase):
    def test_collects_exit_and_junit_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            junit = root / "junit.xml"
            junit.write_text(
                '<testsuite><testcase classname="a" name="ok"/></testsuite>',
                encoding="utf-8",
            )
            collection = collect_commands(
                root,
                [
                    CommandSpec("unit", ("python3", "-c", "print('ok')")),
                    CommandSpec(
                        "junit",
                        ("python3", "-c", "pass"),
                        result_format="junit",
                        junit_path="junit.xml",
                    ),
                ],
                phase="post",
                receipt_dir=root / "receipts",
            )
            self.assertEqual([item["exit_code"] for item in collection["commands"]], [0, 0])
            self.assertEqual(collection["commands"][1]["junit"]["tests"], {"a::ok": "pass"})

    def test_junit_regressions_only_attribute_pass_to_failure(self):
        baseline = {"a::ok": "pass", "a::broken": "fail"}
        post = {"a::ok": "fail", "a::broken": "pass"}
        result = compare_junit(baseline, post)
        self.assertEqual(result["regressions"], ["a::ok"])
        self.assertEqual(result["fixes"], ["a::broken"])

    def test_parse_junit_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "junit.xml"
            path.write_text(
                '<testsuite><testcase classname="a" name="x"/><testcase classname="a" name="x"/></testsuite>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(Exception, "duplicate JUnit"):
                parse_junit(path)
