from __future__ import annotations

import json
import hashlib
import time
import uuid
from pathlib import Path

from agent_workflow.util import sha256_file
from tests.conftest import (
    InstalledProduct,
    fake_agent_path,
    git_repo,
    wait_for_status,
    write_config,
)


def _run_dir(env: dict[str, str], session_id: str) -> Path:
    return Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id


def _write_control_intent(bridge: Path, session_id: str, *, sequence: int, request_id: str,
                          kind: str = "progress") -> None:
    intent = {
        "schema": "agent-workflow/control-intent/v1",
        "request_id": request_id,
        "session_id": session_id,
        "sequence": sequence,
        "kind": kind,
        "actor": "fixture-child",
        "content": "matrix request",
        "correlation_id": None,
        "outcome": None,
        "completion_sha256": None,
        "terminal": None,
    }
    intent["digest"] = "sha256:" + hashlib.sha256(
        json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (bridge / f"intent-{request_id}-{sequence}.json").write_text(
        json.dumps(intent, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )


def _wait_for_path(path: Path) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not path.is_dir():
        time.sleep(0.02)
    assert path.is_dir()


def test_installed_control_intent_matrix_is_durable_correlated_and_append_only(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    cases = ("duplicate", "malformed", "stale", "post-exit")
    for case in cases:
        session_id = f"bridge-matrix-{case}"
        repo = tmp_path / case
        git_repo(repo)
        prompt = tmp_path / f"{case}.md"
        prompt.write_text("Exercise one control-intent matrix row.\n", encoding="utf-8")
        env = dict(product_env)
        env["FAKE_AGENT_MODE"] = "post-exit-intent" if case == "post-exit" else "slow"
        env["FAKE_AGENT_DELAY"] = "1.0"
        installed_product.json(
            "launch", session_id, repo, prompt, "--tier", "low", "--no-interactive", "--",
            fake_agent_path, env=env,
        )
        bridge = repo / ".agent-workflow-handoff" / session_id / "control-intents"
        if case != "post-exit":
            _wait_for_path(bridge)
            request_id = str(uuid.uuid4())
            _write_control_intent(bridge, session_id, sequence=1, request_id=request_id,
                                  kind="bogus" if case == "malformed" else "progress")
            if case == "duplicate":
                _write_control_intent(bridge, session_id, sequence=2, request_id=request_id)
            elif case == "stale":
                _write_control_intent(bridge, session_id, sequence=3, request_id=str(uuid.uuid4()))
        status = wait_for_status(env, session_id)
        assert status["status"] == "completed"
        run = _run_dir(env, session_id)
        raw_lines = (run / "control-intents.jsonl").read_text().splitlines()
        rows = [json.loads(line) for line in raw_lines]
        assert rows
        assert len(rows) == len({row["file"] for row in rows}) == len(raw_lines)
        assert [row["sequence"] for row in rows] == sorted(row["sequence"] for row in rows)
        expected = {
            "duplicate": {"applied", "rejected"},
            "malformed": {"rejected"},
            "stale": {"applied", "rejected"},
            "post-exit": {"rejected"},
        }[case]
        assert {row["outcome"] for row in rows} == expected
        if case == "duplicate":
            assert any("duplicate control request" in row["reason"] for row in rows)
        if case in {"malformed", "stale", "post-exit"}:
            assert any(row["outcome"] == "rejected" for row in rows)
        messages = [json.loads(line) for line in (run / "messages.jsonl").read_text().splitlines()]
        errors = [row for row in messages if row["kind"] == "error"]
        request_ids = {row["request_id"] for row in rows}
        matrix_errors = [
            row for row in errors
            if any(request_id in row["content"] for request_id in request_ids)
        ]
        assert matrix_errors


def test_installed_acceptance_capable_review_requires_launch_tier(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "review.md"
    prompt.write_text("Review the committed change and report evidence.\n", encoding="utf-8")

    result = installed_product.run(
        "launch", "review-missing-tier", repo, prompt,
        "--agent-class", "review", "--no-interactive", "--", fake_agent_path,
        env=product_env,
    )
    assert result.returncode != 0
    assert "requires a recorded launch tier" in result.stderr
    assert not _run_dir(product_env, "review-missing-tier").exists()


def test_external_executor_completes_with_sealed_user_visible_evidence(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Inspect the repository and report completion.\n", encoding="utf-8")

    command_contract = installed_product.json(
        "commands", "--role", "implementation", env=product_env
    )
    represented = {item["command"] for item in command_contract["commands"]}
    assert {"progress", "ack", "agent task-complete"} <= represented

    launched = installed_product.json(
        "launch",
        "success-run",
        repo,
        prompt,
        "--tier",
        "low",
        "--no-interactive",
        "--",
        fake_agent_path,
        env=product_env,
    )
    assert launched["session_id"] == "success-run"

    status = wait_for_status(product_env, "success-run")
    assert status["status"] == "completed"
    run = _run_dir(product_env, "success-run")
    assert (run / "final-receipt.json").stat().st_mode & 0o222 == 0
    assert json.loads((run / "completion.json").read_text())["head_revision"] == head
    handoff = repo / ".agent-workflow-handoff" / "success-run"
    launch_prompt = (handoff / "prompt-seen.txt").read_text()
    assert "Inspect the repository" in launch_prompt
    assert "Do not run `--help` for commands represented in the catalog" in launch_prompt
    assert "Host-owned merge, review, acceptance, release, and pane closure" in launch_prompt
    assert (handoff / "completion-template.json").is_file()
    assert "structured non-interactive run" in launch_prompt

    contract = json.loads((run / "launch-contract.json").read_text())
    assert contract["schema"] == "agent-workflow/launch-contract/v2"
    assert contract["command_plan"]["executor_interactive"] is False
    binding = contract["command_catalog"]
    assert binding["role"] == "implementation"
    assert binding["catalog_sha256"] == sha256_file(run / binding["catalog_path"])
    assert binding["card_sha256"] == sha256_file(run / binding["card_path"])
    catalog = json.loads((run / binding["catalog_path"]).read_text())
    assert catalog["schema"] == "agent-workflow/command-catalog/v1"
    assert any(item["command"] == "launch" for item in catalog["commands"])
    card = (run / binding["card_path"]).read_text()
    assert "agent-workflow progress" in card
    assert "agent-workflow worktree create" not in card
    exported = json.loads((handoff / "command-contract-env.json").read_text())
    assert exported == {
        "catalog": str(run / binding["catalog_path"]),
        "card": str(run / binding["card_path"]),
        "cli": binding["cli_invocation"][0],
    }

    review = installed_product.json(
        "review", "success-run", "--actor", "reviewer", "--reason", "evidence checked", env=product_env
    )
    assert review["disposition"] == "reviewed"
    accepted = installed_product.json(
        "accept",
        "success-run",
        "--actor",
        "reviewer",
        "--reason",
        "meets acceptance criteria",
        "--revision",
        head,
        env=product_env,
    )
    assert accepted["disposition"] == "accepted"

    installed_product.json("kill", "success-run", env=product_env)

    archived = installed_product.json(
        "archive",
        "success-run",
        "--verified",
        "--reason",
        "acceptance journey cleanup",
        env=product_env,
    )
    assert len(archived["archived"]) == 1
    assert not run.exists()
    archive_path = Path(archived["archived"][0]["archived"])
    assert (archive_path / "archive-manifest.json").is_file()
    listed = installed_product.json("list", env=product_env)
    assert all(item.get("session_id") != "success-run" for item in listed)


def test_installed_review_without_ticket_seals_completion_and_receipt(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "review.md"
    prompt.write_text("Review the committed change and report evidence.\n", encoding="utf-8")

    installed_product.json(
        "launch", "review-omitted-ticket", repo, prompt,
        "--agent-class", "review", "--tier", "low", "--no-interactive", "--",
        fake_agent_path, env=product_env,
    )
    status = wait_for_status(product_env, "review-omitted-ticket")
    assert status["status"] == "completed"
    assert status["completion_validation_status"] == "valid"
    run = _run_dir(product_env, "review-omitted-ticket")
    contract = json.loads((run / "launch-contract.json").read_text())
    assert contract["ticket_identity"] == {"mode": "omitted", "value": None}
    collection = json.loads((run / "collections" / "completion.json").read_text())
    assert collection["validation_status"] == "valid"
    assert (run / "final-receipt.json").is_file()
    template = json.loads(
        (repo / ".agent-workflow-handoff" / "review-omitted-ticket" / "completion-template.json").read_text()
    )
    assert template["criteria"] == [
        {"id": "<criterion-id>", "result": "not_verified", "evidence": ["<evidence>"]}
    ]
    assert template["commands"] == [
        {
            "argv": ["<command>"],
            "cwd": "/absolute/worktree",
            "exit_code": 0,
            "receipt": "<receipt>",
        }
    ]

    reviewed = installed_product.json(
        "review", "review-omitted-ticket", "--actor", "reviewer", "--reason", "evidence checked",
        env=product_env,
    )
    assert reviewed["disposition"] == "reviewed"
    accepted = installed_product.json(
        "accept", "review-omitted-ticket", "--actor", "reviewer", "--reason", "meets criteria",
        "--revision", head, env=product_env,
    )
    assert accepted["disposition"] == "accepted"


def test_installed_mismatched_ticket_still_fails_review_collection(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "review.md"
    prompt.write_text("Review the implementation ticket.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_RESULT_JSON"] = json.dumps({"ticket_id": "FORGED-REVIEW"})
    installed_product.json(
        "launch", "review-mismatched-ticket", repo, prompt,
        "--ticket", "IMPL-1", "--agent-class", "review", "--tier", "low",
        "--no-interactive", "--", fake_agent_path, env=env,
    )
    status = wait_for_status(env, "review-mismatched-ticket")
    assert status["status"] == "failed"
    assert status["completion_validation_status"] == "invalid"
    collection = json.loads((_run_dir(env, "review-mismatched-ticket") / "collections" / "completion.json").read_text())
    assert "completion ticket_id does not match launch contract" in collection["validation_errors"]


def test_interactive_child_task_complete_uses_bound_cli_and_bridge(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Complete through the bridge.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "task-complete"

    installed_product.json(
        "launch", "bridge-child", repo, prompt, "--tier", "low",
        "--agent-class", "implementation", "--interactive", "--",
        fake_agent_path, env=env,
    )
    status = wait_for_status(env, "bridge-child")
    assert status["status"] == "completed"
    context = installed_product.json("agent", "context", "bridge-child", env=env)
    assert context["state"] == "closed"

    run = _run_dir(env, "bridge-child")
    handoff = repo / ".agent-workflow-handoff" / "bridge-child"
    exported = json.loads((handoff / "command-contract-env.json").read_text())
    assert Path(exported["cli"]).resolve() == installed_product.cli.resolve()
    messages = [json.loads(line) for line in (run / "messages.jsonl").read_text().splitlines()]
    assert any(item["kind"] == "task_complete" and item["actor"] == "fixture-child" for item in messages)
    intents = [json.loads(line) for line in (run / "control-intents.jsonl").read_text().splitlines()]
    assert any(item["outcome"] == "applied" and item["sequence"] == 1 for item in intents)


def test_force_accept_preserves_normal_rejection_and_records_distinct_override(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Complete the fixture task.\n", encoding="utf-8")
    env = dict(product_env)
    installed_product.json(
        "launch", "force-accept-run", repo, prompt, "--tier", "low",
        "--no-interactive", "--", fake_agent_path, env=env,
    )
    assert wait_for_status(env, "force-accept-run")["status"] == "completed"
    run = _run_dir(env, "force-accept-run")

    ordinary = installed_product.run(
        "accept", "force-accept-run", "--actor", "operator",
        "--reason", "ordinary gate should reject", "--revision", head, env=env,
    )
    assert ordinary.returncode == 2
    assert "prior reviewed" in ordinary.stderr
    forced = installed_product.json(
        "force-accept", "force-accept-run", "--actor", "operator",
        "--reason", "documented emergency local override",
        "--acknowledge", "FORCE-ACCEPT", env=env,
    )
    assert forced["disposition"] == "force-accepted"
    receipt_path = run / "force-accept-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema"] == "agent-workflow/force-accept-receipt/v1"
    assert receipt["session_id"] == "force-accept-run"
    assert receipt["final_receipt_sha256"]
    assert "acceptance requires a prior reviewed disposition" in receipt["normal_gate_failures"]
    assert receipt_path.stat().st_mode & 0o222 == 0

    listed = installed_product.json("list", env=env)
    assert next(item for item in listed if item["session_id"] == "force-accept-run")["disposition"] == "force-accepted"
    repeated = installed_product.run(
        "force-accept", "force-accept-run", "--actor", "operator",
        "--reason", "repeat", "--acknowledge", "FORCE-ACCEPT", env=env,
    )
    assert repeated.returncode == 2
    assert "already exists" in repeated.stderr


def test_sandboxed_child_terminate_does_not_write_host_state(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Complete and exit normally.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "task-complete-terminate"

    installed_product.json(
        "launch", "bridge-child-terminate", repo, prompt, "--tier", "low",
        "--agent-class", "implementation", "--interactive", "--",
        fake_agent_path, env=env,
    )
    status = wait_for_status(env, "bridge-child-terminate")
    assert status["status"] == "completed"
    assert status["completion_validation_status"] == "valid"
    assert not any("Read-only file system" in item for item in status["pump_errors"])


def test_bridged_task_complete_rejects_invalid_handoff_before_reuse(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Attempt completion with an invalid handoff.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "task-complete"
    env["FAKE_AGENT_EMPTY_COMPLETION"] = "1"
    installed_product.json(
        "launch", "invalid-bridge", repo, prompt, "--tier", "low",
        "--agent-class", "implementation", "--interactive", "--",
        fake_agent_path, env=env,
    )
    status = wait_for_status(env, "invalid-bridge")
    assert status["status"] == "failed"
    context = installed_product.json("agent", "context", "invalid-bridge", env=env)
    assert context["state"] == "busy"
    intents = [json.loads(line) for line in (_run_dir(env, "invalid-bridge") / "control-intents.jsonl").read_text().splitlines()]
    assert any(item["outcome"] == "rejected" and "task completion handoff is invalid" in item["reason"] for item in intents)


def test_bridged_task_complete_binds_the_finalized_completion_digest(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Attempt to replace the completion after task-complete.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "task-complete-mutate"
    installed_product.json(
        "launch", "mutated-bridge", repo, prompt, "--tier", "low",
        "--agent-class", "implementation", "--interactive", "--",
        fake_agent_path, env=env,
    )
    wait_for_status(env, "mutated-bridge")
    context = installed_product.json("agent", "context", "mutated-bridge", env=env)
    assert context["state"] == "busy"
    intents = [
        json.loads(line)
        for line in (_run_dir(env, "mutated-bridge") / "control-intents.jsonl").read_text().splitlines()
    ]
    assert any(
        item["outcome"] == "rejected"
        and "task completion handoff changed after task-complete intent" in item["reason"]
        for item in intents
    )


def test_durable_messages_survive_process_boundaries_and_are_acknowledged(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Wait briefly for steering.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "slow"
    env["FAKE_AGENT_DELAY"] = "30"

    installed_product.json(
        "launch", "message-run", repo, prompt, "--tier", "low", "--no-interactive", "--", fake_agent_path,
        env=env,
    )
    steer = installed_product.json(
        "steer", "message-run", "Check the release docs too.", "--actor", "orchestrator", env=env
    )
    watched = installed_product.json(
        "watch", "message-run", "--after", "0", "--timeout", "0.2", env=env
    )
    assert watched[0]["message_id"] == steer["message_id"]
    ack = installed_product.json(
        "ack", "message-run", steer["message_id"], "Applied", "--actor", "agent", env=env
    )
    assert ack["correlation_id"] == steer["message_id"]
    duplicate = installed_product.json(
        "ack", "message-run", steer["message_id"], "Applied again",
        "--actor", "agent", env=env,
    )
    assert duplicate["duplicate"] is True
    assert duplicate["message_id"] == ack["message_id"]
    installed_product.json(
        "terminate", "message-run", "--grace-seconds", "0", env=env
    )

    replayed = installed_product.json(
        "watch", "message-run", "--after", "0", "--timeout", "0", env=env
    )
    assert [item["kind"] for item in replayed] == ["steer", "ack"]


def test_placeholder_completion_fails_collection_and_terminal_run(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Return a substantive completion report.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_EMPTY_COMPLETION"] = "1"

    installed_product.json(
        "launch", "empty-completion", repo, prompt, "--tier", "low",
        "--no-interactive", "--", fake_agent_path, env=env,
    )
    status = wait_for_status(env, "empty-completion")
    assert status["status"] == "failed"
    assert status["exit_code"] == 1
    assert status["completion_validation_status"] == "invalid"
    assert any("completion:" in item for item in status["pump_errors"])
    collection = json.loads(
        (_run_dir(env, "empty-completion") / "collections" / "completion.json").read_text()
    )
    assert collection["validation_status"] == "invalid"
    assert any(
        "requires at least one acceptance criterion" in item
        for item in collection["validation_errors"]
    )



def test_interactive_agent_reuse_requires_completion_selection_and_correlated_acknowledgement(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "first-assignment.md"
    prompt.write_text("Remain available for a second assignment.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "slow"
    env["FAKE_AGENT_DELAY"] = "4.0"

    installed_product.json(
        "launch",
        "reuse-agent",
        repo,
        prompt,
        "--ticket",
        "REUSE-1",
        "--tier",
        "low",
        "--agent-class",
        "implementation",
        "--interactive",
        "--",
        fake_agent_path,
        env=env,
    )
    initial = installed_product.json("agent", "context", "reuse-agent", env=env)
    assert initial["state"] == "busy"
    assert initial["interactive"] is True
    handoff = repo / ".agent-workflow-handoff" / "reuse-agent"
    (handoff / "completion.json").write_text(json.dumps({
        "schema": "agent-workflow/completion/v1", "session_id": "reuse-agent",
        "ticket_id": "REUSE-1", "pack_id": None, "result": "completed",
        "base_revision": head, "head_revision": head, "changed_files": [],
        "criteria": [{"id": "first-assignment", "result": "pass", "evidence": ["fixture handoff"]}],
        "commands": [{"argv": ["fake-agent", "slow"], "cwd": str(repo), "exit_code": 0, "receipt": "fixture completion"}],
        "unresolved": [], "usage": None,
    }), encoding="utf-8")

    completed = installed_product.json(
        "agent",
        "task-complete",
        "reuse-agent",
        "--actor",
        "acceptance-worker",
        "--summary",
        "First assignment complete",
        "--keep-alive",
        "--tag",
        "acceptance",
        env=env,
    )
    assert completed["state"] == "idle_reusable"

    candidates = installed_product.json(
        "agent",
        "candidates",
        repo,
        "--ticket",
        "REUSE-1",
        "--agent-class",
        "implementation",
        "--tag",
        "acceptance",
        env=env,
    )
    selected = next(item for item in candidates if item["session_id"] == "reuse-agent")
    assert selected["eligible"] is True
    assert selected["auto_reuse_eligible"] is True

    second_prompt = tmp_path / "second-assignment.md"
    second_prompt.write_text("Acknowledge this assignment before continuing.\n", encoding="utf-8")
    requested = installed_product.json(
        "agent",
        "reuse",
        "reuse-agent",
        second_prompt,
        "--actor",
        "orchestrator",
        "--ticket",
        "REUSE-2",
        env=env,
    )
    assert requested["context"]["state"] == "reuse_pending"
    correlation_id = requested["message"]["message_id"]
    watched = installed_product.json(
        "watch", "reuse-agent", "--after", "0", "--timeout", "0", env=env
    )
    assert any(
        item["kind"] == "steer" and item["message_id"] == correlation_id
        for item in watched
    )

    installed_product.json(
        "ack",
        "reuse-agent",
        correlation_id,
        "Second assignment accepted",
        "--actor",
        "acceptance-worker",
        env=env,
    )
    acknowledged = installed_product.json("agent", "context", "reuse-agent", env=env)
    assert acknowledged["state"] == "busy"
    assert acknowledged["reuse_count"] == 1
    wait_for_status(env, "reuse-agent")


def test_pending_reuse_cannot_seal_as_completed(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Remain available briefly.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "slow"
    env["FAKE_AGENT_DELAY"] = "4.0"
    installed_product.json("launch", "pending-reuse", repo, prompt, "--ticket", "REUSE-PENDING", "--tier", "low", "--agent-class", "implementation", "--interactive", "--", fake_agent_path, env=env)
    handoff = repo / ".agent-workflow-handoff" / "pending-reuse"
    (handoff / "completion.json").write_text(json.dumps({
        "schema": "agent-workflow/completion/v1", "session_id": "pending-reuse", "ticket_id": "REUSE-PENDING", "pack_id": None, "result": "completed", "base_revision": head, "head_revision": head, "changed_files": [],
        "criteria": [{"id": "fixture", "result": "pass", "evidence": ["fixture handoff"]}],
        "commands": [{"argv": ["fake-agent", "slow"], "cwd": str(repo), "exit_code": 0, "receipt": "fixture completion"}], "unresolved": [], "usage": None,
    }), encoding="utf-8")
    installed_product.json("agent", "task-complete", "pending-reuse", "--actor", "acceptance-worker", "--summary", "First assignment complete", "--keep-alive", env=env)
    second_prompt = tmp_path / "second.md"
    second_prompt.write_text("No acknowledgement.\n", encoding="utf-8")
    requested = installed_product.json("agent", "reuse", "pending-reuse", second_prompt, "--actor", "orchestrator", "--ticket", "REUSE-PENDING-2", env=env)
    assert requested["context"]["state"] == "reuse_pending"
    status = wait_for_status(env, "pending-reuse")
    assert status["status"] == "failed"
    assert any("pending assignment" in item for item in status["pump_errors"])
    final_status = json.loads((_run_dir(env, "pending-reuse") / "final-status.json").read_text())
    assert final_status["status"] == "failed"
    assert (_run_dir(env, "pending-reuse") / "final-receipt.json").is_file()

def test_executor_failure_is_terminal_sealed_and_restartable(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Fail intentionally.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "fail"

    installed_product.json(
        "launch", "failed-run", repo, prompt, "--tier", "low", "--no-interactive", "--", fake_agent_path,
        env=env,
    )
    failed = wait_for_status(env, "failed-run")
    assert failed["status"] == "failed"
    assert failed["exit_code"] == 7
    assert (_run_dir(env, "failed-run") / "final-receipt.json").is_file()

    restarted = installed_product.json("restart", "failed-run", "--new-session", "failed-run-retry", env=env)
    assert restarted["retry_of"] == "failed-run"
    retry = wait_for_status(env, "failed-run-retry")
    assert retry["status"] == "failed"


def test_restart_ignores_tampered_status_projection(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Retry from immutable launch authority.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "fail"

    installed_product.json(
        "launch", "tamper-run", repo, prompt, "--tier", "low", "--no-interactive", "--", fake_agent_path,
        env=env,
    )
    wait_for_status(env, "tamper-run")
    run = _run_dir(env, "tamper-run")
    status_path = run / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update(
        {
            "status": "running",
            "command_path": str(tmp_path / "attacker-command.json"),
            "workdir": str(tmp_path / "attacker-worktree"),
            "prompt_path": str(tmp_path / "attacker-prompt.md"),
            "prompt_source": str(tmp_path / "attacker-prompt.md"),
            "prompt_pack_root": str(tmp_path / "attacker-pack"),
            "ticket_id": "ATTACKER-TICKET",
            "pack_id": "attacker-pack",
            "tier": "attacker-tier",
            "evaluation_path": str(tmp_path / "attacker-evaluation.json"),
        }
    )
    status_path.write_text(json.dumps(status), encoding="utf-8")

    env["FAKE_AGENT_MODE"] = "success"
    restarted = installed_product.json(
        "restart", "tamper-run", "--new-session", "tamper-run-retry", env=env
    )
    assert restarted["retry_of"] == "tamper-run"
    retry = wait_for_status(env, "tamper-run-retry")
    assert retry["status"] == "completed"
    retry_contract = json.loads(
        (_run_dir(env, "tamper-run-retry") / "launch-contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert retry_contract["worktree"]["path"] == str(repo)
    assert retry_contract["prompt"]["source"] == str(prompt)
    assert retry_contract["session"]["tier"] == "low"


def test_structured_provider_events_reach_normalized_sealed_evidence(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Emit structured evidence.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"

    installed_product.json(
        "launch",
        "structured-run",
        repo,
        prompt,
        "--config",
        config,
        "--executor",
        "codex",
        "--structured",
        "--no-interactive",
        "--tier",
        "low",
        env=env,
    )
    wait_for_status(env, "structured-run")
    evidence = json.loads((_run_dir(env, "structured-run") / "provider-evidence.json").read_text())
    assert evidence["usage_complete"] is True
    assert evidence["aggregate"]["input_tokens"] == 5
    assert evidence["aggregate"]["cached_input_tokens"] == 1
    assert evidence["aggregate"]["output_tokens"] == 3
