import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agent_workflow.eval.trials import collect_trials, extract_trial, load_trials
from agent_workflow.metrics import write_execution_evidence
from agent_workflow.provider_evidence import write_provider_evidence
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json
from run_fixtures import write_run_contracts


class TrialEvidenceTests(unittest.TestCase):
    def _run(self, root: Path, name: str) -> Path:
        run = root / name
        write_run_contracts(run, session_id=name)
        (run / "executor-events.jsonl").write_text(
            '{"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":2,"provider_billed_cost":0.1,"currency":"USD"}}\n',
            encoding="utf-8",
        )
        provider = write_provider_evidence(run, stream_format="codex-jsonl", executor="codex")
        provenance = __import__("json").loads((run / "run-provenance.json").read_text())
        provenance["usage"] = provider["aggregate"]
        provenance["provider_evidence"] = {
            "path": "provider-evidence.json",
            "sha256": __import__("hashlib").sha256((run / "provider-evidence.json").read_bytes()).hexdigest(),
            "usage_complete": True,
            "capture_complete": True,
        }
        atomic_write_json(run / "run-provenance.json", provenance)
        write_execution_evidence(run, elapsed_seconds=1.5)
        seal_run(run, session_id=name)
        final_hash = hashlib.sha256((run / "final-receipt.json").read_bytes()).hexdigest()
        score = {
            "schema": "agent-workflow/score-receipt/v1",
            "scorer": {"id": "schema_validity", "version": "1"},
            "final_receipt_sha256": final_hash,
            "verdict": "pass",
            "facts": {"contracts": ["completion", "provenance"]},
            "evidence": [
                {"path": "completion.json", "sha256": hashlib.sha256((run / "completion.json").read_bytes()).hexdigest()},
                {"path": "run-provenance.json", "sha256": hashlib.sha256((run / "run-provenance.json").read_bytes()).hexdigest()},
            ],
        }
        encoded = json.dumps(score, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        atomic_write_json(run / "scores" / f"schema_validity-{digest}.json", score, mode=0o444)
        atomic_write_json(
            run / "scores" / "score-set.json",
            {
                "schema": "agent-workflow/score-set/v1",
                "final_receipt_sha256": final_hash,
                "verdict": "pass",
                "scores": [score],
            },
        )
        return run

    def test_extract_and_collect_explicit_sealed_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(Path(tmp), "trial-1")
            trial = extract_trial(run)
            self.assertEqual(5, trial["tokens"])
            self.assertEqual("pass", trial["verdict"])
            self.assertEqual(0.1, trial["provider_billed_cost"])
            self.assertIsNone(trial["local_estimated_cost"])
            output = Path(tmp) / "evidence.json"
            collect_trials([run], output)
            self.assertEqual([trial], load_trials(output))

    def test_unsealed_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, include_final=False)
            with self.assertRaisesRegex(Exception, "final receipt"):
                extract_trial(run)
    def test_writable_content_addressed_score_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(Path(tmp), "trial-writable-score")
            score_file = next(
                path for path in (run / "scores").glob("schema_validity-*.json")
            )
            score_file.chmod(0o644)
            with self.assertRaisesRegex(Exception, "read-only"):
                extract_trial(run)

    def test_forged_score_set_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(Path(tmp), "trial-forged")
            atomic_write_json(
                run / "scores" / "score-set.json",
                {"verdict": "pass", "scores": []},
            )
            with self.assertRaisesRegex(Exception, "score set"):
                extract_trial(run)
