from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import InstalledProduct, git_repo, wait_for_status, write_config


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
