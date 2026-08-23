from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.conftest import InstalledProduct, git_repo, wait_for_status


def test_installed_orchestrator_accepts_explicit_keep_alive_child(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "keep-alive-child"
    git_repo(repo)
    prompt = tmp_path / "keep-alive.md"
    prompt.write_text("keep alive fixture\n", encoding="utf-8")
    child_env = dict(product_env)
    child_env.update({"FAKE_AGENT_MODE": "slow", "FAKE_AGENT_DELAY": "4.0"})
    installed_product.json(
        "launch", "keep-alive-child", repo, prompt, "--interactive", "--", fake_agent_path,
        env=child_env,
    )
    handoff = repo / ".agent-workflow-handoff" / "keep-alive-child"
    handoff.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
    (handoff / "completion.json").write_text(json.dumps({
        "schema": "agent-workflow/completion/v1", "session_id": "keep-alive-child", "ticket_id": None,
        "pack_id": None, "result": "completed", "base_revision": head, "head_revision": head,
        "changed_files": [], "criteria": [{"id": "fixture", "result": "pass", "evidence": ["keep-alive fixture"]}],
        "commands": [{"argv": ["fake-agent", "slow"], "cwd": str(repo), "exit_code": 0, "receipt": "fixture completion"}],
        "unresolved": [], "usage": None,
    }), encoding="utf-8")
    installed_product.json(
        "agent", "task-complete", "keep-alive-child", "--actor", "fixture-child",
        "--summary", "keep-alive complete", "--keep-alive", env=child_env,
    )
    installed_product.json("orchestrator", "registry", "create", "keep-alive-root", env=product_env)
    installed_product.json(
        "orchestrator", "registry", "register", "keep-alive-root", "keep-alive-child", env=product_env,
    )
    imported = installed_product.json(
        "orchestrator", "inbox", "import", "keep-alive-root", env=product_env,
    )
    assert imported["count"] == 1
    assert imported["imported"][0]["state"] == "idle_reusable"
    installed_product.json(
        "terminate", "keep-alive-child", "--grace-seconds", "0", env=child_env
    )

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
    assert all(event["state"] is None for event in events)
    assert all("summary" not in event for event in events)

    repeated = installed_product.json(
        "orchestrator", "inbox", "import", "main-orchestrator", env=product_env
    )
    assert repeated["count"] == 2
    assert all(item["duplicate"] for item in repeated["imported"])
    assert len(installed_product.json("orchestrator", "inbox", "list", "main-orchestrator", env=product_env)) == 2

    with_content = installed_product.json(
        "orchestrator", "inbox", "read", "main-orchestrator", "--include-content",
        env=product_env,
    )
    assert [item["summary"] for item in with_content] == [
        "fixture assignment complete",
        "fixture assignment complete",
    ]

    state_runs = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow" / "runs"
    child_one_messages = state_runs / "child-one" / "messages.jsonl"
    child_two_messages = state_runs / "child-two" / "messages.jsonl"
    installed_product.json(
        "orchestrator", "registry", "unregister", "main-orchestrator", "child-two",
        "--state", "abandoned", env=product_env,
    )
    assert child_two_messages.is_file(), "unregister must not delete child evidence"
    installed_product.json(
        "orchestrator", "registry", "unregister", "main-orchestrator", "child-one",
        "--state", "completed", env=product_env,
    )
    terminal_import = installed_product.run(
        "orchestrator", "inbox", "import", "main-orchestrator",
        "--session-id", "child-one", env=product_env,
    )
    assert terminal_import.returncode == 2
    assert child_one_messages.is_file(), "terminal retention must preserve source evidence"
    for session_id in ("child-one", "child-two"):
        installed_product.json(
            "terminate", session_id, "--grace-seconds", "0", env=child_env
        )


def test_installed_orchestrator_watch_replays_once_and_resumes_from_cursor(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    print("WATCH start", flush=True)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("watch fixture\n", encoding="utf-8")
    child_env = dict(product_env)
    child_env["FAKE_AGENT_MODE"] = "task-complete"
    repo = tmp_path / "watch-child"
    git_repo(repo)
    print("WATCH launch", flush=True)
    installed_product.json(
        "launch", "watch-child", repo, prompt, "--interactive", "--", fake_agent_path,
        env=child_env,
    )
    print("WATCH launched", flush=True)
    assert wait_for_status(child_env, "watch-child")["status"] == "completed"
    print("WATCH completed", flush=True)
    print("WATCH create registry", flush=True)
    installed_product.json("orchestrator", "registry", "create", "watcher", env=product_env)
    installed_product.json(
        "orchestrator", "registry", "register", "watcher", "watch-child", env=product_env
    )

    # No wake hint is required for correctness: the bounded replay cycle sees
    # the durable child journal even when the hint is lost.
    print("WATCH first cycle", flush=True)
    first = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01",
        "--poll-seconds", "0.01", "--max-cycles", "1", env=product_env
    )
    assert first["state"] == "completed"
    assert first["advanced"] >= 1
    assert first["imported"] == 1

    # Durable replay remains idempotent without terminal wake hints.
    print("WATCH first done", flush=True)
    second = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01",
        "--poll-seconds", "0.01", "--max-cycles", "2", env=product_env
    )
    print("WATCH second done", flush=True)
    assert second["advanced"] == 0
    assert len(installed_product.json("orchestrator", "inbox", "list", "watcher", env=product_env)) == 1
    print("WATCH terminate", flush=True)
    installed_product.json(
        "terminate", "watch-child", "--grace-seconds", "0", env=child_env
    )

