import tempfile
import unittest
from pathlib import Path

from agent_workflow.eval.trials import collect_trials, extract_trial, load_trials
from agent_workflow.metrics import write_execution_evidence
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json
from run_fixtures import write_run_contracts


class TrialEvidenceTests(unittest.TestCase):
    def _run(self, root: Path, name: str) -> Path:
        run = root / name
        write_run_contracts(run, session_id=name)
        provenance = __import__("json").loads((run / "run-provenance.json").read_text())
        provenance["usage"] = {"input_tokens": 3, "output_tokens": 2, "cost": 0.1, "currency": "USD"}
        atomic_write_json(run / "run-provenance.json", provenance)
        write_execution_evidence(run, elapsed_seconds=1.5)
        seal_run(run, session_id=name)
        atomic_write_json(run / "scores" / "score-set.json", {"verdict": "pass"})
        return run

    def test_extract_and_collect_explicit_sealed_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self._run(Path(tmp), "trial-1")
            trial = extract_trial(run)
            self.assertEqual(5, trial["tokens"])
            self.assertEqual("pass", trial["verdict"])
            output = Path(tmp) / "evidence.json"
            collect_trials([run], output)
            self.assertEqual([trial], load_trials(output))

    def test_unsealed_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "run"
            write_run_contracts(run, include_final=False)
            with self.assertRaisesRegex(Exception, "final receipt"):
                extract_trial(run)
