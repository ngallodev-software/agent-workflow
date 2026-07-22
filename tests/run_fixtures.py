from pathlib import Path

from agent_workflow.receipts import initial_completion, initial_provenance
from agent_workflow.util import atomic_write_json, sha256_file


def write_run_contracts(
    root: Path, *, session_id: str = "test-run", include_final: bool = True
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, content in {
        "prompt.md": "task\n",
        "launch-prompt.md": "task\n",
        "completion.md": "completion\n",
        "executor-events.jsonl": "",
        "executor-stderr.log": "",
        "output.log": "",
        "patch.diff": "",
    }.items():
        (root / name).write_text(content, encoding="utf-8")
    atomic_write_json(
        root / "command.json",
        {
            "schema": "agent-workflow/command/v1",
            "argv": ["cat"],
            "shell": "cat",
            "executor": None,
            "stream_format": "text",
        },
    )
    atomic_write_json(
        root / "source-baseline.json",
        {
            "schema": "agent-workflow/source-baseline/v1",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "components": {
                "primary": {"path": str(root), "head": "", "branch": "", "dirty": False}
            },
        },
    )
    atomic_write_json(
        root / "completion.json",
        initial_completion(
            session_id=session_id,
            ticket_id=None,
            pack_id=None,
            base_revision=None,
        ),
    )
    atomic_write_json(
        root / "collections" / "completion.json",
        {
            "schema": "agent-workflow/completion-collection/v1",
            "session_id": session_id,
            "adapter": "native",
            "adapter_version": "1",
            "source_path": None,
            "source_sha256": None,
            "canonical_mapping": "identity",
            "canonical_sha256": sha256_file(root / "completion.json"),
            "validation_status": "valid",
            "validation_errors": [],
            "collected_at": "2026-01-01T00:00:00+00:00",
            "stored_path": "completion.json",
        },
    )
    atomic_write_json(
        root / "run-provenance.json",
        initial_provenance(
            session_id=session_id,
            executor=None,
            argv=["cat"],
            stream_format="text",
            executor_version=None,
            prompt_sha256="0" * 64,
            launch_prompt_sha256="1" * 64,
            config_sha256=None,
            pack_manifest_sha256=None,
            source_revision=None,
            worktree=root,
            environment={},
        ),
    )
    status = {
        "schema": "agent-workflow/session-status/v2",
        "session_id": session_id,
        "status": "launched",
        "disposition": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "workdir": str(root),
        "prompt_path": str(root / "prompt.md"),
        "log_path": str(root / "output.log"),
        "completion_collection_path": str(root / "collections" / "completion.json"),
        "completion_validation_status": "valid",
    }
    atomic_write_json(root / "status.json", status)
    if include_final:
        atomic_write_json(root / "final-status.json", {**status, "status": "completed"})
