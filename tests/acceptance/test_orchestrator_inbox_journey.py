from __future__ import annotations

import json
import uuid
from pathlib import Path

from agent_workflow.util import atomic_write_json, utc_now
from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status


def _run_dir(env: dict[str, str], session_id: str) -> Path:
    return Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id


def _add_verified_completion(env: dict[str, str], session_id: str, summary: str) -> None:
    run = _run_dir(env, session_id)
    assignment_id = str(uuid.uuid4())
    now = utc_now()
    atomic_write_json(
        run / "agent-context.json",
        {
            "schema": "agent-workflow/agent-context/v1",
            "session_id": session_id,
            "agent_name": None,
            "agent_class": "implementation",
            "executor": "fixture",
            "model": None,
            "interactive": True,
            "provider_session_id": None,
            "repository_root": None,
            "worktree": json.loads((run / "launch-contract.json").read_text())["worktree"]["path"],
            "source_revision": None,
            "state": "idle_reusable",
            "current_assignment": None,
            "completed_assignments": [{"assignment_id": assignment_id, "summary": summary}],
            "reuse_count": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    (run / "assignments.jsonl").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/assignment-event/v1",
                "sequence": 1,
                "timestamp": now,
                "event": "task_completed",
                "session_id": session_id,
                "assignment_id": assignment_id,
                "actor": "child",
                "ticket_id": None,
                "pack_id": None,
                "correlation_id": None,
                "summary": summary,
                "tags": [],
                "files": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "events.jsonl").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/lifecycle-event/v1",
                "sequence": 1,
                "timestamp": now,
                "dimension": "assignment",
                "prior": "busy",
                "new": "idle_reusable",
                "actor": "child",
                "reason": "verified completion",
                "receipt_refs": ["assignments.jsonl", "agent-context.json"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    message_id = str(uuid.uuid4())
    (run / "messages.jsonl").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/session-message/v1",
                "sequence": 1,
                "message_id": message_id,
                "session_id": session_id,
                "timestamp": now,
                "direction": "child_to_parent",
                "kind": "task_complete",
                "actor": "child",
                "content": summary,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_installed_cli_registers_verified_children_and_deduplicates_inbox(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture child\n", encoding="utf-8")
    for session_id in ("child-one", "child-two"):
        repo = tmp_path / session_id
        git_repo(repo)
        installed_product.json(
            "launch", session_id, repo, prompt, "--no-interactive", "--", fake_agent_path,
            env=product_env,
        )
        wait_for_status(product_env, session_id)
        _add_verified_completion(product_env, session_id, f"{session_id} complete")

    created = installed_product.json(
        "orchestrator", "registry", "create", "main-orchestrator", env=product_env
    )
    assert "/orchestrators/" in created["path"]
    assert "main-orchestrator" not in Path(created["path"]).parent.name
    for session_id in ("child-one", "child-two"):
        installed_product.json(
            "orchestrator", "registry", "register", "main-orchestrator", session_id,
            env=product_env,
        )

    imported = installed_product.json(
        "orchestrator", "inbox", "import", "main-orchestrator", env=product_env
    )
    assert imported["count"] == 2
    events = installed_product.json(
        "orchestrator", "inbox", "list", "main-orchestrator", "--after", "0", env=product_env
    )
    assert [event["sequence"] for event in events] == [1, 2]
    assert [event["kind"] for event in events] == ["agent_idle", "agent_idle"]
    assert all("summary" not in event for event in events)

    repeated = installed_product.json(
        "orchestrator", "inbox", "import", "main-orchestrator", env=product_env
    )
    assert repeated["count"] == 2
    assert all(item["duplicate"] for item in repeated["imported"])
    assert len(installed_product.json("orchestrator", "inbox", "list", "main-orchestrator", env=product_env)) == 2

