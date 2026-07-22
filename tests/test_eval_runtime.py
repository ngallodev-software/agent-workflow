import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_workflow.config import defaults
from agent_workflow.eval.scoring import score_trial
from agent_workflow.receipts import verify_seal
from agent_workflow.sessions import launch


class EvaluationRuntimeTests(unittest.TestCase):
    def test_collectors_run_before_seal_and_rescore_without_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            work.mkdir()
            (work / "answer.txt").write_text("before\n", encoding="utf-8")
            prompt = root / "prompt.md"
            prompt.write_text("update answer\n", encoding="utf-8")
            evaluation = root / "evaluation.json"
            evaluation.write_text(
                json.dumps(
                    {
                        "schema": "agent-workflow/evaluation-plan/v1",
                        "dataset_split": "development",
                        "task_ids": ["P0-01"],
                        "repetitions": 1,
                        "timeout_seconds": 60,
                        "scorers": ["acceptance_commands", "writable_scope"],
                        "sandbox": "docker",
                        "acceptance_commands": [
                            {
                                "id": "answer",
                                "argv": [
                                    "python3",
                                    "-c",
                                    "from pathlib import Path; assert Path('answer.txt').is_file()",
                                ],
                            }
                        ],
                        "scope": {"writable_paths": ["answer.txt"]},
                    }
                ),
                encoding="utf-8",
            )
            settings = defaults(root / "missing.toml")
            settings = settings.__class__(
                **{**settings.__dict__, "state_root": root / "state"}
            )
            receiver = (
                "from pathlib import Path; import sys; "
                "sys.stdin.read(); Path('answer.txt').write_text('after\\n')"
            )
            with (
                patch("agent_workflow.sessions.tmux.session_exists", return_value=False),
                patch("agent_workflow.sessions.tmux.create_session") as create,
                patch("agent_workflow.sessions.tmux.pane_info", return_value=None),
            ):
                launched = launch(
                    settings,
                    session_id="eval-runtime",
                    workdir=work,
                    prompt_path=prompt,
                    explicit_command=["python3", "-c", receiver],
                    ticket_id="P0-01",
                    evaluation_path=evaluation,
                )
            subprocess.run([create.call_args.args[2]], check=True)
            run = Path(launched["prompt_path"]).parent
            status = json.loads((run / "status.json").read_text(encoding="utf-8"))
            verify_seal(run, expected_sha256=status["final_receipt_sha256"])
            self.assertTrue((run / "scope" / "scope-post.json").is_file())
            self.assertTrue((run / "collections" / "commands-post.json").is_file())
            result = score_trial(
                run,
                output_dir=run / "scores",
                expected_final_receipt_sha256=status["final_receipt_sha256"],
            )
            self.assertEqual(result["verdict"], "pass")
