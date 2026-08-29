from __future__ import annotations

import json
import os
import pty
import subprocess
import time
from pathlib import Path

import pytest

from tests.conftest import InstalledProduct, git_repo, wait_for_status, write_config
from agent_workflow.run_lifecycle import transition_execution_path


def _run_dir(env: dict[str, str], agent_run_id: str) -> Path:
    return Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / agent_run_id


def test_installed_cli_exposes_headless_agent_run_surface(
    installed_product: InstalledProduct, product_env: dict[str, str]
) -> None:
    expected_version = (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    assert installed_product.run("--version", env=product_env, check=True).stdout.strip() == f"agent-workflow {expected_version}"

    help_text = installed_product.run("--help", env=product_env, check=True).stdout
    for command in ("doctor", "agent-run", "workflow", "eval", "pack", "worktree", "supervisor"):
        assert command in help_text
    assert " launch " not in f" {help_text} "

    agent_run_help = installed_product.run("agent-run", "--help", env=product_env, check=True).stdout
    for command in ("prepare", "start", "status", "steer", "progress", "ack", "interrupt", "terminate", "restart"):
        assert command in agent_run_help

    doctor = installed_product.json("doctor", env=product_env)
    assert doctor["version"] == expected_version
    assert doctor["checks"]["required_commands_present"] is True
    assert set(doctor["commands"]) >= {"git", "bash", "python3", "tar", "zstd"}

    config = installed_product.json("config", "show", env=product_env)
    assert "terminal" not in config
    assert "backend" not in config
    assert Path(config["paths"]["state_root"]).is_absolute()

    catalog = installed_product.json("commands", "--format", "json", env=product_env)
    represented = {item["command"] for item in catalog["commands"]}
    assert {"agent-run prepare", "agent-run start", "agent-run status", "agent task-complete", "worktree closeout"} <= represented
    assert "launch" not in represented


def test_headless_agent_run_prepare_start_and_provenance_journey(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Complete the fixture task.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    private_alias = "private-review-runtime-sentinel"
    private_model = "gpt-5.6-luna"
    with config.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n[runtime_aliases.private-review-runtime-sentinel]\n"
            'executor = "codex"\n'
            f'model = "{private_model}"\n'
            'reasoning_effort = "medium"\n'
            "\n[roles.bindings]\n"
            f'review = "{private_alias}"\n'
        )
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"

    prepared = installed_product.json(
        "agent-run", "prepare", "headless-basic", repo, prompt,
        "--config", config, "--role", "review",
        "--tier", "medium", "--structured", env=env,
    )
    assert prepared["status"] == "prepared"
    assert prepared["worker_mode"] == "headless"
    assert prepared["role"] == "review"

    run = _run_dir(env, "headless-basic")
    contract = json.loads((run / "agent-run-contract.json").read_text(encoding="utf-8"))
    assert contract["schema"] == "agent-workflow/agent-run-contract/v1"
    assert contract["agent_run"]["id"] == "headless-basic"
    assert contract["worker_plan"]["mode"] == "headless"
    serialized = json.dumps(contract).lower()
    assert "pane_id" not in serialized
    assert "terminal_backend" not in serialized

    started = installed_product.json("agent-run", "start", "headless-basic", env=env)
    assert started["status"] in {"running", "completed"}
    status = wait_for_status(env, "headless-basic")
    assert status["status"] == "completed"
    assert status["worker_mode"] == "headless"
    assert status.get("worker_id")
    assert status.get("worker_pid") != status.get("worker_id")

    public_status = installed_product.json("agent-run", "status", "headless-basic", env=env)
    public_context = installed_product.json("agent", "context", "headless-basic", env=env)
    handoff = repo / ".agent-workflow-handoff" / "headless-basic"
    public_handoff = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(handoff.rglob("*"))
        if path.is_file()
    )
    public_encoded = json.dumps(
        [prepared, started, public_status, public_context, public_handoff],
        sort_keys=True,
    ).lower()
    for private_identity in (private_alias, "codex", private_model):
        assert private_identity.lower() not in public_encoded
    assert not (repo / ".delegations" / "headless-basic").exists()

    command = json.loads((run / "command.json").read_text(encoding="utf-8"))
    provenance = json.loads((run / "run-provenance.json").read_text(encoding="utf-8"))
    assert command["runtime_alias"] == private_alias
    assert command["executor"] == "codex"
    assert command["model"] == private_model
    assert provenance["executor"] == "codex"
    assert provenance["model"] == private_model
    assert provenance["executable"]["resolved_path"] == str(fake_agent_path.resolve())
    assert len(provenance["executable"]["sha256"]) == 64
    assert (run / "final-receipt.json").is_file()


def test_external_prepare_is_host_independent_and_process_control_is_unavailable(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "external-repo"
    git_repo(repo)
    prompt = tmp_path / "external.md"
    prompt.write_text("Prepare only.\n", encoding="utf-8")
    env = dict(product_env)

    prepared = installed_product.json(
        "agent-run", "prepare", "external-run", repo, prompt,
        "--worker-mode", "external", "--interactive", "--", fake_agent_path,
        env=env,
    )
    assert prepared["status"] == "prepared"
    assert prepared["worker_mode"] == "external"
    assert prepared.get("worker_pid") is None
    run = _run_dir(env, "external-run")
    runner_text = (run / "run.sh").read_text(encoding="utf-8")
    assert "--interactive" not in runner_text
    assert "--non-interactive" in runner_text
    contract = json.loads((run / "agent-run-contract.json").read_text(encoding="utf-8"))
    assert contract["worker_plan"]["noninteractive_argv"]
    assert len(contract["worker_plan"]["noninteractive_command_sha256"]) == 64

    start = installed_product.run("--json", "agent-run", "start", "external-run", env=env)
    assert start.returncode == 2
    assert "external" in start.stderr.lower()

    # External lifecycle operations do not guess at runtime-host control.
    status_path = _run_dir(env, "external-run") / "status.json"
    status = json.loads(status_path.read_text())
    status["status"] = "running"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    interrupted = installed_product.json("agent-run", "interrupt", "external-run", env=env)
    terminated = installed_product.json("agent-run", "terminate", "external-run", "--grace-seconds", "0", env=env)
    assert interrupted["outcome"] == "unavailable"
    assert terminated["outcome"] == "unavailable"

    transition_execution_path(
        run / "status.json",
        "failed",
        actor="test",
        reason="simulate terminal external worker failure",
    )
    restarted = installed_product.json(
        "agent-run", "restart", "external-run", "--new-agent-run-id", "external-retry", env=env,
    )
    assert restarted["status"] == "prepared"
    retry_contract = json.loads((_run_dir(env, "external-retry") / "agent-run-contract.json").read_text())
    assert retry_contract["worker_plan"]["mode"] == "external"
    assert retry_contract["worker_plan"]["argv"] == contract["worker_plan"]["argv"]
    assert retry_contract["agent_run"]["agent_name"] == contract["agent_run"]["agent_name"]


@pytest.mark.parametrize("host_mode", ["pipe", "pty"])
def test_generated_external_launcher_records_durable_start_in_each_host_mode(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
    host_mode: str,
) -> None:
    """Execute the published external contract instead of only inspecting it."""
    repo = tmp_path / f"external-{host_mode}"
    git_repo(repo)
    prompt = tmp_path / f"{host_mode}.md"
    prompt.write_text("Run through the external launch contract.\n", encoding="utf-8")
    env = dict(product_env)
    env.update({"FAKE_AGENT_MODE": "slow", "FAKE_AGENT_DELAY": "0.5"})
    installed_product.json(
        "agent-run", "prepare", f"external-{host_mode}", repo, prompt,
        "--worker-mode", "external", "--interactive", "--", fake_agent_path,
        env=env,
    )
    run = _run_dir(env, f"external-{host_mode}")
    launch = run / "run.sh"
    launch.chmod(launch.stat().st_mode | 0o111)

    master_fd: int | None = None
    slave_fd: int | None = None
    if host_mode == "pty":
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(
            [str(launch)], cwd=repo, env=env, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = None
        # The fixture consumes stdin to EOF; send the terminal EOF character
        # while retaining the pseudo-terminal for the interactive launch.
        os.write(master_fd, b"\x04")
    else:
        process = subprocess.Popen(
            [str(launch)], cwd=repo, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    try:
        status_path = run / "status.json"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if status_path.is_file():
                status = json.loads(status_path.read_text(encoding="utf-8"))
                if status.get("status") == "running":
                    break
            time.sleep(0.02)
        else:
            raise AssertionError("generated external launcher never recorded running")

        assert process.wait(timeout=10) == 0
        lifecycle = [
            json.loads(line)
            for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert [event["new"] for event in lifecycle[:2]] == ["prepared", "running"]
        assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == "completed"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        if master_fd is not None:
            os.close(master_fd)
        if slave_fd is not None:
            os.close(slave_fd)
