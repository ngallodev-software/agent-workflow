from __future__ import annotations

import json
import subprocess
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
    for command in ("prepare", "start", "start-external", "status", "steer", "progress", "ack", "interrupt", "terminate", "restart"):
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
    assert {"agent-run prepare", "agent-run start", "agent-run start-external", "agent-run status", "agent task-complete", "worktree closeout"} <= represented
    assert "launch" not in represented


def test_installed_delegate_is_importable_and_idempotent(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "delegate-repo"
    git_repo(repo)
    prompt = tmp_path / "delegate.md"
    prompt.write_text("Prepare this delegation.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    first = installed_product.json(
        "delegate", "delegate-idempotent", prompt, "--workdir", repo,
        "--worker-mode", "external", "--interactive", "--config", config,
        env=product_env,
    )
    second = installed_product.json(
        "delegate", "delegate-idempotent", prompt, "--workdir", repo,
        "--worker-mode", "external", "--interactive", "--config", config,
        env=product_env,
    )
    assert first["state"] == "prepared"
    assert second["state"] == "prepared"
    assert second["reused_existing_run"] is True


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

    start = installed_product.run("--json", "agent-run", "start", "external-run", env=env)
    assert start.returncode == 2
    assert "external" in start.stderr.lower()

    binding = installed_product.json(
        "agent-run", "bind-external", "external-run", "test-runtime", "worker-a", env=env
    )
    assert binding["generation"] == 1
    started = installed_product.json(
        "agent-run", "start-external", "external-run", "test-runtime", "worker-a",
        "--generation", "1", env=env,
    )
    assert started["status"] == "running"
    lifecycle = [
        json.loads(line)["new"]
        for line in (_run_dir(env, "external-run") / "events.jsonl").read_text().splitlines()
        if line
    ]
    assert lifecycle[:2] == ["prepared", "running"]
    started_again = installed_product.json(
        "agent-run", "start-external", "external-run", "test-runtime", "worker-a",
        "--generation", "1", env=env,
    )
    assert started_again["status"] == "running"

    run = _run_dir(env, "external-run")
    handoff = repo / ".agent-workflow-handoff" / "external-run"
    completion = json.loads((handoff / "completion-template.json").read_text())
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    completion.update(
        {
            "base_revision": head,
            "head_revision": head,
            "criteria": [{"id": "external-start", "result": "pass", "evidence": ["started"]}],
            "commands": [{"argv": ["external-worker"], "cwd": str(repo), "exit_code": 0, "receipt": "started"}],
        }
    )
    (handoff / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
    completed = installed_product.json(
        "agent", "task-complete", "external-run", "--actor", "external-worker",
        "--summary", "external assignment complete", env=env,
    )
    assert completed["state"] == "closed"

    # External lifecycle operations do not guess at runtime-host control.
    interrupted = installed_product.json("agent-run", "interrupt", "external-run", env=env)
    terminated = installed_product.json("agent-run", "terminate", "external-run", "--grace-seconds", "0", env=env)
    assert interrupted["outcome"] == "unavailable"
    assert terminated["outcome"] == "unavailable"


def test_external_start_rejects_missing_mismatched_and_stale_bindings(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "external.md"
    prompt.write_text("Prepare only.\n", encoding="utf-8")
    for run_id in ("missing-binding", "mismatched-binding", "stale-binding"):
        repo = tmp_path / run_id
        git_repo(repo)
        installed_product.json(
            "agent-run", "prepare", run_id, repo, prompt,
            "--worker-mode", "external", "--interactive", "--", fake_agent_path,
            env=product_env,
        )

    missing = installed_product.run(
        "--json", "agent-run", "start-external", "missing-binding", "runtime", "worker",
        "--generation", "1", env=product_env,
    )
    assert missing.returncode == 2
    assert "not bound" in missing.stderr.lower()

    installed_product.json(
        "agent-run", "bind-external", "mismatched-binding", "runtime", "worker-a", env=product_env
    )
    mismatch = installed_product.run(
        "--json", "agent-run", "start-external", "mismatched-binding", "runtime", "worker-b",
        "--generation", "1", env=product_env,
    )
    assert mismatch.returncode == 2
    assert "does not match" in mismatch.stderr.lower()

    installed_product.json(
        "agent-run", "bind-external", "stale-binding", "runtime", "worker-a", env=product_env
    )
    rebound = installed_product.json(
        "agent-run", "bind-external", "stale-binding", "runtime", "worker-b", env=product_env
    )
    assert rebound["generation"] == 2
    stale = installed_product.run(
        "--json", "agent-run", "start-external", "stale-binding", "runtime", "worker-a",
        "--generation", "1", env=product_env,
    )
    assert stale.returncode == 2
    assert "stale" in stale.stderr.lower()
