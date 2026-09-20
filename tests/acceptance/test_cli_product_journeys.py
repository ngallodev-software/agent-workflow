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
from agent_workflow.receipts import verify_seal_details


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
    assert {
        "agent-run prepare",
        "agent-run start",
        "agent-run status",
        "agent criterion",
        "agent verify",
        "agent complete",
        "worktree closeout",
    } <= represented
    assert "agent task-complete" not in represented
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


def test_headless_codex_scope_includes_linked_worktree_git_directory(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    git_repo(source)
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(source), "worktree", "add", "-q", str(linked), "HEAD"],
        check=True,
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Complete the linked worktree task.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"

    installed_product.json(
        "agent-run", "prepare", "linked-gitdir", linked, prompt,
        "--config", config, "--role", "review", "--tier", "medium",
        "--structured", env=env,
    )

    run = _run_dir(env, "linked-gitdir")
    command = json.loads((run / "command.json").read_text(encoding="utf-8"))["argv"]
    git_dir = subprocess.run(
        ["git", "-C", str(linked), "rev-parse", "--absolute-git-dir"],
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    add_dirs = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "--add-dir"]
    assert git_dir in add_dirs


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
    assert prepared["steering_adapter"] == "external-host-v1"
    assert prepared["steering_supported"] is True
    assert prepared.get("worker_pid") is None
    run = _run_dir(env, "external-run")
    runner_text = (run / "run.sh").read_text(encoding="utf-8")
    assert "--interactive" not in runner_text
    assert "--non-interactive" in runner_text
    contract = json.loads((run / "agent-run-contract.json").read_text(encoding="utf-8"))
    assert contract["worker_plan"]["noninteractive_argv"]
    assert len(contract["worker_plan"]["noninteractive_command_sha256"]) == 64
    assert contract["runtime_policy"]["steering"]["adapter"] == "external-host-v1"
    assert "acknowledge a steer message ID" in (run / "launch-prompt.md").read_text()

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


def test_external_exit_completes_only_after_task_completion_and_rebuilds_receipt(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "external-success"
    git_repo(repo)
    prompt = tmp_path / "external-success.md"
    prompt.write_text("Complete through the external exit contract.\n", encoding="utf-8")
    env = dict(product_env)
    installed_product.json(
        "agent-run", "prepare", "external-success", repo, prompt,
        "--worker-mode", "external", "--interactive", "--ticket", "EXT-HOST-002",
        "--", fake_agent_path, env=env,
    )
    run = _run_dir(env, "external-success")
    binding = installed_product.json(
        "agent-run", "bind-external", "external-success", "host", "worker-host", env=env,
    )
    assert binding["generation"] == 1
    installed_product.json(
        "agent-run", "start-external", "external-success", "host", "worker-host",
        "--generation", "1", env=env,
    )
    criterion = installed_product.json(
        "agent", "criterion", "external-success", "external-exit", "pass",
        "--evidence", "ordered integration journey", env=env,
    )
    assert criterion["criterion"]["result"] == "pass"
    verification = installed_product.json(
        "agent", "verify", "--cwd", repo, "external-success", "--",
        installed_product.python, "-c", "raise SystemExit(0)", env=env,
    )
    assert verification["ok"] is True
    completed = installed_product.json(
        "agent", "complete", "external-success", "--result", "completed", env=env,
    )
    assert completed["state"] == "finalized"
    assert not (run / "final-receipt.json").exists()
    exit_observation = installed_product.json(
        "agent-run", "external-exit", "external-success", "--generation", "1",
        "--actor", "operator", "--reason", "host observed worker exit", env=env,
    )
    assert exit_observation["completion_reported"] is True
    assert "pid" not in exit_observation and "returncode" not in exit_observation
    assert not any(key in exit_observation for key in ("review", "acceptance"))
    finalized = installed_product.json("agent-run", "finalize", "external-success", env=env)
    assert finalized["outcome"] == "finalized"
    assert finalized["terminal_status"] == "completed"
    receipt, _ = verify_seal_details(run)
    assert [item["path"] for item in receipt["artifacts"]].count("external-worker-exit.json") == 1
    repaired = installed_product.json("agent-run", "repair", "external-success", env=env)
    assert repaired["status"] == "completed"


def test_external_delivery_rejects_stale_and_unbound_generations(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "external-delivery"
    git_repo(repo)
    prompt = tmp_path / "external-delivery.md"
    prompt.write_text("Exercise host delivery.\n", encoding="utf-8")
    env = dict(product_env)
    installed_product.json(
        "agent-run", "prepare", "external-delivery", repo, prompt,
        "--worker-mode", "external", "--interactive", "--", fake_agent_path,
        env=env,
    )
    first = installed_product.json(
        "agent-run", "bind-external", "external-delivery", "host", "worker-1", env=env,
    )
    installed_product.json(
        "agent-run", "start-external", "external-delivery", "host", "worker-1",
        "--generation", str(first["generation"]), env=env,
    )
    steer = installed_product.json(
        "agent-run", "steer", "external-delivery", "deliver this", "--actor", "parent", env=env,
    )
    second = installed_product.json(
        "agent-run", "bind-external", "external-delivery", "host", "worker-2", env=env,
    )
    stale = installed_product.run(
        "agent-run", "report-external-delivery", "external-delivery", steer["message_id"],
        "--generation", str(first["generation"]), "--attempt", "1", "--outcome", "delivered",
        "--reason", "old host", env=env,
    )
    assert stale.returncode == 2
    assert "stale" in stale.stderr
    delivered = installed_product.json(
        "agent-run", "report-external-delivery", "external-delivery", steer["message_id"],
        "--generation", str(second["generation"]), "--attempt", "1", "--outcome", "delivered",
        "--reason", "current host", env=env,
    )
    assert delivered["acknowledged"] is False
    installed_product.json("agent-run", "unbind-external", "external-delivery", env=env)
    unbound = installed_product.run(
        "agent-run", "report-external-delivery", "external-delivery", steer["message_id"],
        "--generation", str(second["generation"]), "--attempt", "2", "--outcome", "delivered",
        "--reason", "unbound host", env=env,
    )
    assert unbound.returncode == 2
    assert "not bound" in unbound.stderr


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
