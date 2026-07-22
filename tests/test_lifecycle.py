import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.events import reconstruct_lifecycle
from agent_workflow.lifecycle import record
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json, sha256_file
from run_fixtures import write_run_contracts


class LifecycleTests(unittest.TestCase):
    def _completed_run(self, root: Path) -> tuple[object, Path]:
        settings = defaults(root / "missing.toml")
        settings = settings.__class__(
            **{**settings.__dict__, "state_root": root / "state"}
        )
        run = root / "state" / "runs" / "life-test"
        write_run_contracts(run, session_id="life-test")
        completion = json.loads((run / "completion.json").read_text(encoding="utf-8"))
        completion.update(result="completed", head_revision="abc123", unresolved=[])
        atomic_write_json(run / "completion.json", completion)
        atomic_write_json(
            run / "evaluation-runtime.json",
            {
                "schema": "agent-workflow/evaluation-runtime/v1",
                "scorers": ["acceptance_commands"],
            },
        )
        seal_run(run, session_id="life-test")
        status = json.loads((run / "status.json").read_text(encoding="utf-8"))
        status.update(
            status="completed",
            disposition=None,
            final_receipt_path=str(run / "final-receipt.json"),
            final_receipt_sha256=sha256_file(run / "final-receipt.json"),
            tier="medium",
        )
        atomic_write_json(run / "status.json", status)
        scores = run / "scores"
        scores.mkdir()
        score_receipts = []
        for scorer_id in ("schema_validity", "acceptance_commands"):
            score_receipt = {
                "schema": "agent-workflow/score-receipt/v1",
                "scorer": {"id": scorer_id, "version": "1"},
                "final_receipt_sha256": status["final_receipt_sha256"],
                "verdict": "pass",
                "facts": {},
                "evidence": [],
            }
            encoded = json.dumps(
                score_receipt, sort_keys=True, separators=(",", ":")
            ).encode()
            digest = hashlib.sha256(encoded).hexdigest()
            atomic_write_json(scores / f"{scorer_id}-{digest}.json", score_receipt)
            score_receipts.append(score_receipt)
        atomic_write_json(
            scores / "score-set.json",
            {
                "schema": "agent-workflow/score-set/v1",
                "final_receipt_sha256": status["final_receipt_sha256"],
                "verdict": "pass",
                "scores": score_receipts,
            },
        )
        return settings, run

    def test_review_then_accept_appends_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run = self._completed_run(Path(tmp))
            reviewed = record(
                settings,
                "life-test",
                action="reviewed",
                actor="reviewer",
                reason="deterministic gates pass",
            )
            accepted = record(
                settings,
                "life-test",
                action="accepted",
                actor="reviewer",
                reason="approved",
                revision="abc123",
            )
            self.assertEqual(reviewed["disposition"], "reviewed")
            self.assertEqual(accepted["disposition"], "accepted")
            self.assertEqual(len(list((run / "receipts").glob("*.json"))), 2)
            reconstructed = reconstruct_lifecycle(run / "events.jsonl")
            self.assertEqual(reconstructed["state"]["review"], "accepted")

    def test_accept_rejects_revision_mismatch_and_failed_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run = self._completed_run(Path(tmp))
            record(
                settings,
                "life-test",
                action="reviewed",
                actor="reviewer",
                reason="reviewed",
            )
            with self.assertRaisesRegex(WorkflowError, "revision mismatch"):
                record(
                    settings,
                    "life-test",
                    action="accepted",
                    actor="reviewer",
                    reason="wrong revision",
                    revision="wrong",
                )
            score_path = run / "scores" / "score-set.json"
            score = json.loads(score_path.read_text(encoding="utf-8"))
            score["verdict"] = "fail"
            score["scores"][0]["verdict"] = "fail"
            changed_receipt = score["scores"][0]
            changed_digest = hashlib.sha256(
                json.dumps(
                    changed_receipt, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            atomic_write_json(
                run
                / "scores"
                / f"{changed_receipt['scorer']['id']}-{changed_digest}.json",
                changed_receipt,
            )
            atomic_write_json(score_path, score)
            with self.assertRaisesRegex(WorkflowError, "passing deterministic"):
                record(
                    settings,
                    "life-test",
                    action="accepted",
                    actor="reviewer",
                    reason="failed gates",
                    revision="abc123",
                )

    def test_high_risk_acceptance_rejects_executor_self_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run = self._completed_run(Path(tmp))
            status_path = run / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status.update(tier="high", executor="same-actor")
            atomic_write_json(status_path, status)
            record(
                settings,
                "life-test",
                action="reviewed",
                actor="same-actor",
                reason="self review",
            )
            with self.assertRaisesRegex(WorkflowError, "independent .*review"):
                record(
                    settings,
                    "life-test",
                    action="accepted",
                    actor="same-actor",
                    reason="self acceptance",
                    revision="abc123",
                )

    def test_high_risk_acceptance_rejects_self_review_then_other_acceptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run = self._completed_run(Path(tmp))
            status_path = run / "status.json"
            status = json.loads(status_path.read_text(encoding="utf-8"))
            status.update(tier="critical", executor="executor-id")
            atomic_write_json(status_path, status)
            record(
                settings,
                "life-test",
                action="reviewed",
                actor="executor-id",
                reason="self review",
            )
            with self.assertRaisesRegex(WorkflowError, "independent prior review"):
                record(
                    settings,
                    "life-test",
                    action="accepted",
                    actor="different-acceptor",
                    reason="attempted bypass",
                    revision="abc123",
                )

    def test_review_rejects_omitted_required_scorer(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings, run = self._completed_run(Path(tmp))
            score_path = run / "scores" / "score-set.json"
            score = json.loads(score_path.read_text(encoding="utf-8"))
            score["scores"] = [
                item
                for item in score["scores"]
                if item["scorer"]["id"] == "schema_validity"
            ]
            atomic_write_json(score_path, score)
            with self.assertRaisesRegex(WorkflowError, "missing required scorers"):
                record(
                    settings,
                    "life-test",
                    action="reviewed",
                    actor="reviewer",
                    reason="incomplete scores",
                )
