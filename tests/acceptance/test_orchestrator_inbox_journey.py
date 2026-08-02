from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from agent_workflow.tmux import orchestrator_wakeup_channel
from tests.conftest import InstalledProduct, git_repo, wait_for_status


def test_installed_cli_registers_verified_children_and_deduplicates_inbox(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture child\n", encoding="utf-8")
    child_env = dict(product_env)
    child_env["FAKE_AGENT_MODE"] = "task-complete"
    for session_id in ("child-one", "child-two"):
        repo = tmp_path / session_id
        git_repo(repo)
        installed_product.json(
            "launch", session_id, repo, prompt, "--interactive", "--", fake_agent_path,
            env=child_env,
        )
        assert wait_for_status(child_env, session_id)["status"] == "completed"

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


def test_installed_orchestrator_watch_replays_once_and_resumes_from_cursor(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("watch fixture\n", encoding="utf-8")
    child_env = dict(product_env)
    child_env["FAKE_AGENT_MODE"] = "task-complete"
    repo = tmp_path / "watch-child"
    git_repo(repo)
    installed_product.json(
        "launch", "watch-child", repo, prompt, "--interactive", "--", fake_agent_path,
        env=child_env,
    )
    assert wait_for_status(child_env, "watch-child")["status"] == "completed"
    installed_product.json("orchestrator", "registry", "create", "watcher", env=product_env)
    installed_product.json(
        "orchestrator", "registry", "register", "watcher", "watch-child", env=product_env
    )

    # No wake hint is required for correctness: the bounded replay cycle sees
    # the durable child journal even when the hint is lost.
    first = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01",
        "--poll-seconds", "0.01", "--max-cycles", "1", env=product_env
    )
    assert first["state"] == "completed"
    assert first["advanced"] >= 1
    assert first["imported"] == 1

    registry = installed_product.json("orchestrator", "registry", "inspect", "watcher", env=product_env)
    child = registry["children"][0]
    # The registry path is intentionally hashed; derive the projection path
    # from the configured state root and the public child identity.
    state_root = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    key = hashlib.sha256("watcher".encode()).hexdigest()
    cursor_path = state_root / "orchestrators" / key / "cursors" / hashlib.sha256(child["identity_digest"].encode()).hexdigest()
    cursor_path = cursor_path.with_suffix(".json")
    cursor_path.unlink()
    rebuilt = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01", "--max-cycles", "1", env=product_env
    )
    assert rebuilt["advanced"] == 0
    cursor_path.write_text("{invalid", encoding="utf-8")
    repaired = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01", "--max-cycles", "1", env=product_env
    )
    assert repaired["advanced"] == 0
    quarantine = cursor_path.parent / "cursor-quarantine"
    assert any(json.loads(path.read_text(encoding="utf-8"))["content_redacted"] for path in quarantine.glob("*.json"))

    # Duplicate best-effort hints remain harmless because source identity and
    # the durable cursor make normalization idempotent.
    channel = orchestrator_wakeup_channel("watcher")
    subprocess.run(["tmux", "wait-for", "-S", channel], env=product_env, check=False)
    subprocess.run(["tmux", "wait-for", "-S", channel], env=product_env, check=False)
    second = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01",
        "--poll-seconds", "0.01", "--max-cycles", "2", env=product_env
    )
    assert second["advanced"] == 0
    assert len(installed_product.json("orchestrator", "inbox", "list", "watcher", env=product_env)) == 1


@pytest.mark.parametrize(
    ("projection", "quarantined"),
    (("absent", False), ("corrupt", True), ("oversized", True), ("inconsistent", True), ("pending", True)),
)
def test_installed_orchestrator_watch_rebuilds_status_projection(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
    projection: str,
    quarantined: bool,
) -> None:
    prompt = tmp_path / f"{projection}.md"
    prompt.write_text("status repair fixture\n", encoding="utf-8")
    repo = tmp_path / f"status-{projection}"
    git_repo(repo)
    child_env = dict(product_env)
    child_env["FAKE_AGENT_MODE"] = "task-complete"
    installed_product.json(
        "launch", f"status-child-{projection}", repo, prompt, "--interactive", "--", fake_agent_path,
        env=child_env,
    )
    assert wait_for_status(child_env, f"status-child-{projection}")["status"] == "completed"
    installed_product.json("orchestrator", "registry", "create", f"status-{projection}", env=product_env)
    installed_product.json(
        "orchestrator", "registry", "register", f"status-{projection}", f"status-child-{projection}",
        env=product_env,
    )
    installed_product.json(
        "orchestrator", "watch", f"status-{projection}", "--interval-seconds", "0.01", "--max-cycles", "1",
        env=product_env,
    )
    state_root = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    key = hashlib.sha256(f"status-{projection}".encode()).hexdigest()
    directory = state_root / "orchestrators" / key
    status = directory / "supervisor-status.json"
    if projection == "absent":
        status.unlink()
    elif projection == "corrupt":
        status.write_text("{not-json", encoding="utf-8")
    elif projection == "oversized":
        status.write_bytes(b"x" * (64 * 1024 + 1))
    elif projection == "pending":
        status.write_text(
            json.dumps(
                {
                    "schema": "agent-workflow/orchestrator-supervisor-status/v1",
                    "schema_version": 1,
                    "state": "completed",
                    "cycle": 1,
                    "advanced": 1,
                    "imported": 1,
                    "reconstructed": False,
                    "pending_acknowledgements": ["00000000-0000-0000-0000-000000000000"],
                    "pending_acknowledgement_digests": {
                        "00000000-0000-0000-0000-000000000000": "sha256:" + "0" * 64,
                    },
                    "pending_actions": [],
                    "pending_action_digests": {},
                    "updated_at": "not-authoritative",
                }
            ),
            encoding="utf-8",
        )
    else:
        status.write_text(
            json.dumps(
                {
                    "schema": "agent-workflow/orchestrator-supervisor-status/v1",
                    "schema_version": 1,
                    "state": "wrong",
                    "cycle": 999,
                    "advanced": 999,
                    "imported": 999,
                    "reconstructed": False,
                    "updated_at": "not-authoritative",
                }
            ),
            encoding="utf-8",
        )

    repaired = installed_product.json(
        "orchestrator", "watch", f"status-{projection}", "--interval-seconds", "0.01", "--max-cycles", "1",
        env=product_env,
    )
    assert repaired["state"] == "completed"
    rebuilt = json.loads(status.read_text(encoding="utf-8"))
    assert rebuilt["state"] == "completed"
    assert rebuilt["cycle"] == 1
    assert rebuilt["advanced"] == 0
    assert rebuilt["imported"] == 0
    events = [json.loads(line) for line in (directory / "supervisor-events.jsonl").read_text().splitlines()]
    assert events[-3]["reason"] == "startup"
    assert events[-3]["status_reconstructed"] is True
    quarantine = directory / "supervisor-status-quarantine"
    assert any(quarantine.glob("*.json")) is quarantined
