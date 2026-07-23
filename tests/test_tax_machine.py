import json
import tempfile
import unittest
from pathlib import Path

from agent_workflow.errors import WorkflowError
from agent_workflow.runner import _collect_completion
from agent_workflow.receipts import seal_run
from agent_workflow.tax_machine import discover, validate_completion, validate_job
from run_fixtures import write_run_contracts


def make_pack(root: Path) -> tuple[Path, Path]:
    (root / "schemas").mkdir(parents=True)
    (root / "MANIFEST.json").write_text("{}", encoding="utf-8")
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "tax-job", "type": "object", "required": ["ticket"], "properties": {"ticket": {"type": "string"}}}
    (root / "schemas" / "job.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    schema["$id"] = "tax-completion"
    (root / "schemas" / "completion.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    job = root / "job.json"
    job.write_text('{"ticket":"C-1"}', encoding="utf-8")
    prompt = root / "ticket.md"
    prompt.write_text("ticket", encoding="utf-8")
    return job, prompt


class TaxMachineAdapterTests(unittest.TestCase):
    def test_discovers_validates_and_rejects_unsafe_paths_and_refs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "pack"
            job, prompt = make_pack(root)
            pack = discover(prompt)
            self.assertIsNotNone(pack)
            assert pack is not None
            self.assertEqual(validate_job(pack, job)["ticket"], "C-1")
            linked_job = root / "linked-job.json"
            linked_job.symlink_to(job)
            with self.assertRaisesRegex(WorkflowError, "regular non-symlink"):
                validate_job(pack, linked_job)
            self.assertEqual(validate_completion(pack, b'{"ticket":"C-1"}')["ticket"], "C-1")
            (root / "schemas" / "completion.schema.json").write_text(json.dumps({"$id":"tax-completion", "$ref":"../outside.json"}), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "escapes adapter boundary"):
                validate_completion(pack, b'{}')
            (root / "MANIFEST.json").unlink()
            (root / "MANIFEST.json").symlink_to(root / "job.json")
            with self.assertRaisesRegex(WorkflowError, "regular and non-symlink"):
                discover(prompt)

    def test_external_completion_is_sealed_separately_and_cannot_replace_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_root = root / "pack"
            job, _ = make_pack(pack_root)
            state, work = root / "state", root / "work"
            work.mkdir()
            write_run_contracts(state, session_id="tax-c", include_final=False)
            handoff = work / ".agent-workflow-handoff" / "tax-c"
            handoff.mkdir(parents=True)
            (handoff / "completion.json").write_text('{"ticket":"C-1"}', encoding="utf-8")
            status_path = state / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status.update({"handoff_dir": str(handoff), "pack_adapter": "tax-machine", "prompt_pack_root": str(pack_root)})
            status_path.write_text(json.dumps(status), encoding="utf-8")
            receipt = _collect_completion(state, work)
            self.assertEqual(receipt["validation_status"], "valid", receipt)
            self.assertEqual(receipt["canonical_mapping"], "not_mappable_current_schema")
            self.assertTrue((state / "external" / "tax-machine" / "completion.json").is_file())
            self.assertEqual(json.loads((state / "completion.json").read_text())["result"], "blocked")

    def test_tax_snapshot_files_are_hashed_in_final_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_root = root / "pack"
            job, prompt = make_pack(pack_root)
            pack = discover(prompt)
            assert pack is not None
            state = root / "state"
            write_run_contracts(state, session_id="tax-seal")
            snapshots = pack.snapshot(state, job)
            receipt = seal_run(state, session_id="tax-seal")
            artifacts = {entry["path"]: entry["sha256"] for entry in receipt["artifacts"]}
            for snapshot in snapshots.values():
                self.assertEqual(artifacts[snapshot["stored_path"]], snapshot["stored_sha256"])
