from __future__ import annotations

import json
import os
import time
from pathlib import Path

from tests.conftest import InstalledProduct, fake_agent_path, git_repo


def test_installed_supervisor_detects_no_progress_and_probes_once(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Remain alive without useful progress.\n", encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                "schema_version = 1",
                "[terminal]",
                "stall_minutes = 1",
                "[git]",
                "require_clean_source = false",
                "[supervisor]",
                "probe_stalled = true",
                "max_remediation_attempts = 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "hang"
    env["FAKE_AGENT_DELAY"] = "30"
    installed_product.json(
        "launch",
        "supervisor-stall",
        repo,
        prompt,
        "--config",
        config,
        "--no-interactive",
        "--",
        fake_agent_path,
        env=env,
    )

    run = (
        Path(env["XDG_STATE_HOME"])
        / "agent-workflow"
        / "runs"
        / "supervisor-stall"
    )
    deadline = time.time() + 10
    while time.time() < deadline and not (run / "heartbeat.json").is_file():
        time.sleep(0.05)
    assert (run / "heartbeat.json").is_file()
    output = run / "output.log"
    output.touch(exist_ok=True)
    old = time.time() - 120
    for name in (
        "output.log",
        "executor-stderr.log",
        "executor-events.jsonl",
        "terminal-events.jsonl",
        "messages.jsonl",
        "control-intents.jsonl",
        "steering-delivery.jsonl",
        "completion.json",
    ):
        path = run / name
        if path.exists():
            os.utime(path, (old, old))

    first = installed_product.json(
        "supervisor",
        "once",
        "--config",
        config,
        "--session",
        "supervisor-stall",
        "--no-capture-interactive",
        env=env,
    )
    second = installed_product.json(
        "supervisor",
        "once",
        "--config",
        config,
        "--session",
        "supervisor-stall",
        "--no-capture-interactive",
        env=env,
    )

    assert first["run_count"] == 1
    assert first["runs"][0]["observed_state"] == "possibly_stalled"
    assert first["runs"][0]["remediations"][0]["rule_id"] == "SAFE-PROBE-STALL-v1"
    assert (
        first["runs"][0]["remediations"][0]["details"]["verification"]
        == "authoritative_post_action_observation"
    )
    assert (
        first["runs"][0]["remediations"][0]["details"]["post_action_observation"][
            "observed_state"
        ]
        == "running"
    )
    assert second["runs"][0]["remediations"] == []
    remediation = [
        json.loads(line)
        for line in (run / "remediation-events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["rule_id"] for event in remediation] == ["SAFE-PROBE-STALL-v1"]
    assert (run / "incident-events.jsonl").is_file()
    assert (run / "run-health-samples.jsonl").is_file()

    installed_product.run("terminate", "supervisor-stall", env=env, timeout=15)


def test_installed_supervisor_surfaces_permission_wait_without_granting_it(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo-permission"
    git_repo(repo)
    prompt = tmp_path / "permission-prompt.md"
    prompt.write_text("Attempt the requested operation.\n", encoding="utf-8")
    config = tmp_path / "permission-config.toml"
    config.write_text("[git]\nrequire_clean_source = false\n", encoding="utf-8")

    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "hang"
    env["FAKE_AGENT_DELAY"] = "30"
    installed_product.json(
        "launch",
        "supervisor-permission",
        repo,
        prompt,
        "--config",
        config,
        "--no-interactive",
        "--",
        fake_agent_path,
        env=env,
    )
    run = (
        Path(env["XDG_STATE_HOME"])
        / "agent-workflow"
        / "runs"
        / "supervisor-permission"
    )
    deadline = time.time() + 10
    while time.time() < deadline and not (run / "heartbeat.json").is_file():
        time.sleep(0.05)
    assert (run / "heartbeat.json").is_file()
    (run / "executor-stderr.log").write_text(
        "Approval required. Allow this command?\n", encoding="utf-8"
    )

    report = installed_product.json(
        "supervisor",
        "once",
        "--config",
        config,
        "--session",
        "supervisor-permission",
        "--no-capture-interactive",
        env=env,
    )
    observed = report["runs"][0]
    assert observed["observed_state"] == "blocked_permission"
    assert observed["incident"]["category"] == "permission_wait"
    assert observed["remediations"] == []
    permission = [
        json.loads(line)
        for line in (run / "permission-events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert permission[-1]["state"] == "pending"
    assert permission[-1]["principal"] is None
    installed_product.run("terminate", "supervisor-permission", env=env, timeout=15)


def test_installed_supervisor_repairs_corrupt_status_from_immutable_evidence(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    from tests.conftest import wait_for_status

    repo = tmp_path / "repo-repair"
    git_repo(repo)
    prompt = tmp_path / "repair-prompt.md"
    prompt.write_text("Complete normally.\n", encoding="utf-8")
    config = tmp_path / "repair-config.toml"
    config.write_text("[git]\nrequire_clean_source = false\n", encoding="utf-8")
    env = dict(product_env)
    installed_product.json(
        "launch",
        "supervisor-repair",
        repo,
        prompt,
        "--config",
        config,
        "--no-interactive",
        "--",
        fake_agent_path,
        env=env,
    )
    wait_for_status(env, "supervisor-repair")
    run = (
        Path(env["XDG_STATE_HOME"])
        / "agent-workflow"
        / "runs"
        / "supervisor-repair"
    )
    status = run / "status.json"
    status.chmod(0o600)
    status.write_text("{corrupt", encoding="utf-8")

    report = installed_product.json(
        "supervisor",
        "once",
        "--config",
        config,
        "--session",
        "supervisor-repair",
        env=env,
    )
    assert report["repaired_projection_count"] == 1
    repaired = json.loads(status.read_text(encoding="utf-8"))
    assert repaired["status"] == "completed"
    events = [
        json.loads(line)
        for line in (run / "remediation-events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[-1]["rule_id"] == "SAFE-REPAIR-STATUS-v1"
    assert events[-1]["outcome"] == "applied"
