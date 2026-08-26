#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_workflow import __version__
from agent_workflow.agent_runs import _write_launch_prompt
from agent_workflow.roles import load_roles
from agent_workflow.command_catalog import (
    encode_command_catalog,
    filter_catalog,
    render_command_markdown,
    runtime_command_catalog,
)

SCHEMA = "agent-workflow/agent-efficiency-baseline/v1"

# This is a measurement inventory, not a second lifecycle implementation.  The
# sequences describe the currently documented model-decision surface so later
# phases can prove that a facade removed decisions without removing authority.
SCENARIOS: dict[str, tuple[str, ...]] = {
    "simple_headless_delegation": (
        "worktree create",
        "agent-run prepare",
        "agent-run start",
        "agent-run status",
    ),
    "review_and_accept": (
        "agent-run review",
        "agent-run accept",
    ),
    "workflow_resume": (
        "workflow start",
        "workflow status",
        "workflow resume",
    ),
    "recovery_inspection": (
        "agent-run status",
        "agent-run repair",
        "agent-run finalize",
    ),
}

ROLE_CASES = {
    "implementation": {"agent_class": "implementation", "interactive": False, "detached_interactive": True},
    "review": {"agent_class": "review", "interactive": False, "detached_interactive": False},
    "orchestrator": {"agent_class": "orchestrator", "interactive": False, "detached_interactive": False},
}


def _approx_tokens(byte_count: int) -> int:
    # Deliberately dependency-free and clearly labeled as an estimate.  Exact
    # provider tokenization is inappropriate for a provider-opaque baseline.
    return math.ceil(byte_count / 4)


def _measurement_role_metadata(role: str) -> tuple[str, str, str | None]:
    if role in {"implementation", "review"}:
        public_role = load_roles()[role]
        return public_role.role_id, public_role.digest, public_role.instructions_markdown

    # The orchestrator command-card profile represents the host surface, not a
    # delegated public AgentRole.  Give the measurement prompt a deterministic
    # host-only identity without adding an orchestrator role to the public role
    # catalog or leaking a private runtime binding into the measurement.
    role_id = "orchestrator"
    role_digest = hashlib.sha256(b"agent-workflow/measurement-role/orchestrator/v1").hexdigest()
    return role_id, role_digest, None


def _launch_context_overhead_bytes(role: str, catalog: dict) -> int:
    case = ROLE_CASES[role]
    role_id, role_digest, role_instructions = _measurement_role_metadata(role)
    with tempfile.TemporaryDirectory(prefix="aw-efficiency-") as tmp:
        state_dir = Path(tmp)
        prompt = state_dir / "prompt.md"
        prompt_text = "Representative delegated task.\n"
        prompt.write_text(prompt_text, encoding="utf-8")
        handoff = state_dir / "handoff"
        handoff.mkdir()
        command_artifacts = {"role": role}
        launch = _write_launch_prompt(
            state_dir,
            agent_run_id=f"phase0-{role}",
            agent_name=None,
            agent_class=str(case["agent_class"]),
            role_id=role_id,
            role_digest=role_digest,
            role_instructions=role_instructions,
            tier="medium",
            retry_of=None,
            created_at="2026-08-25T00:00:00+00:00",
            prompt_source=prompt,
            prompt_pack_root=None,
            handoff_dir=handoff,
            interactive=bool(case["interactive"]),
            detached_interactive=bool(case["detached_interactive"]),
            command_artifacts=command_artifacts,
            steering_adapter="unsupported",
        )
        total = len(launch.read_bytes())
        return total - len(prompt_text.encode("utf-8"))


def measure() -> dict:
    catalog = runtime_command_catalog(no_plugins=True)
    roles: dict[str, dict[str, int]] = {}
    for role in ROLE_CASES:
        selected = filter_catalog(catalog, role)
        card = render_command_markdown(catalog, role=role).encode("utf-8")
        launch_overhead = _launch_context_overhead_bytes(role, catalog)
        machine_catalog = encode_command_catalog(selected)
        roles[role] = {
            "command_count": len(selected["commands"]),
            "command_card_bytes": len(card),
            "machine_catalog_bytes": len(machine_catalog),
            "machine_catalog_approx_tokens": _approx_tokens(len(machine_catalog)),
            "command_card_approx_tokens": _approx_tokens(len(card)),
            "launch_context_overhead_bytes": launch_overhead,
            "launch_context_overhead_approx_tokens": _approx_tokens(launch_overhead),
        }

    full_card = render_command_markdown(catalog, role="all").encode("utf-8")
    primary_skill = (ROOT / "skills" / "agent-workflow" / "SKILL.md").read_bytes()
    commands_by_name = {str(item["command"]): item for item in catalog["commands"]}
    prepare = commands_by_name["agent-run prepare"]
    prepare_flags = {
        flag
        for option in prepare["options"]
        for flag in option.get("flags", [])
    }

    return {
        "schema": SCHEMA,
        "application_version": __version__,
        "measurement_scope": "static-agent-facing-cost",
        "provider_neutral_token_estimate": "ceil(utf8_bytes/4)",
        "catalog": {
            "leaf_commands": len(catalog["commands"]),
            "full_json_bytes": len(encode_command_catalog(catalog)),
            "full_json_approx_tokens": _approx_tokens(len(encode_command_catalog(catalog))),
            "full_markdown_bytes": len(full_card),
            "full_markdown_approx_tokens": _approx_tokens(len(full_card)),
            "launch_artifact_currently_writes_full_json_for_every_role": True,
        },
        "roles": roles,
        "primary_skill": {
            "bytes": len(primary_skill),
            "approx_tokens": _approx_tokens(len(primary_skill)),
        },
        "documented_cli_decision_surface": {
            name: {"invocations": len(commands), "commands": list(commands)}
            for name, commands in SCENARIOS.items()
        },
        "identity_exposure": {
            "prepare_accepts_executor": "--executor" in prepare_flags,
            "prepare_accepts_model": "--model" in prepare_flags,
            "prepare_accepts_agent_class": "--agent-class" in prepare_flags,
            "opaque_role_interface_present": False,
            "runtime_alias_interface_present": False,
            "normal_contract_surfaces": [
                {"surface": "agent-run prepare", "fields": ["agent_class", "executor", "model"]},
                {"surface": "agent-run status/status.json", "fields": ["agent_class", "executor", "model"]},
                {"surface": "agent context/agent-context.json", "fields": ["agent_class", "executor", "model"]},
                {"surface": "MCP public run status", "fields": ["agent_class", "executor", "model"]},
                {"surface": "workflow snapshot node command", "fields": ["agent_class", "executor", "model"]},
            ],
            "state_artifacts_readable_by_same_account": [
                {"surface": "agent-run-contract.json worker_plan", "fields": ["executor", "model"]},
                {"surface": "command.json", "fields": ["executor", "model"]},
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Agent-Workflow agent-facing efficiency baseline")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path, help="compare the measured value to an existing baseline JSON")
    args = parser.parse_args()

    value = measure()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.check is not None:
        expected = json.loads(args.check.read_text(encoding="utf-8"))
        expected_static = {key: expected.get(key) for key in value}
        if expected_static != value:
            print("agent-efficiency baseline drifted", file=sys.stderr)
            return 1
        print("agent-efficiency baseline: current")
        return 0
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
