"""Filesystem artifacts created before a delegated session process starts."""

from __future__ import annotations

import base64
import json
import shlex
import shutil
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .path import read_regular_file
from .process import run


def _ignore_delegations(workdir: Path) -> None:
    _add_git_exclude(workdir, ".delegations/")


def _add_git_exclude(workdir: Path, entry: str) -> None:
    try:
        result = run(
            ["git", "-C", str(workdir), "rev-parse", "--git-path", "info/exclude"]
        )
    except WorkflowError:
        return
    exclude = Path(result.stdout.strip())
    if not exclude.is_absolute():
        exclude = workdir / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    if entry not in {line.strip() for line in existing.splitlines()}:
        with exclude.open("a", encoding="utf-8") as stream:
            if existing and not existing.endswith("\n"):
                stream.write("\n")
            stream.write(entry + "\n")


def _create_handoff_dir(workdir: Path, session_id: str) -> Path:
    """Create the executor-writable completion boundary in the worktree."""
    _add_git_exclude(workdir, ".agent-workflow-handoff/")
    handoff = workdir / ".agent-workflow-handoff" / session_id
    if handoff.exists() or handoff.is_symlink():
        raise WorkflowError(f"completion handoff already exists: {handoff}")
    handoff.mkdir(parents=True, mode=0o700)
    return handoff.resolve()


def _link_worktree_state(
    workdir: Path,
    session_id: str,
    state_dir: Path,
) -> None:
    _ignore_delegations(workdir)
    delegations = workdir / ".delegations"
    delegations.mkdir(parents=True, exist_ok=True)
    link = delegations / session_id
    if link.exists() or link.is_symlink():
        try:
            if link.resolve() == state_dir.resolve():
                return
        except OSError:
            pass
        raise WorkflowError(f"delegation link already exists: {link}")
    link.symlink_to(state_dir, target_is_directory=True)


def _write_runner(
    state_dir: Path,
    workdir: Path,
    command: list[str],
    *,
    python_executable: str,
    session_id: str = "unknown-session",
    prompt_source: Path | None = None,
    prompt_pack_root: Path | None = None,
    handoff_dir: Path | None = None,
    completion_template_path: Path | None = None,
    command_artifacts: dict[str, Any] | None = None,
    stream_format: str = "text",
    interactive: bool = False,
    close_tmux_on_exit: bool = False,
) -> Path:
    prompt = state_dir / "prompt.md"
    launch_prompt = state_dir / "launch-prompt.md"
    if not launch_prompt.exists() and prompt.exists():
        shutil.copy2(prompt, launch_prompt)
    prompt_source = prompt_source or prompt
    runner = state_dir / "run.sh"
    source_root = Path(__file__).resolve().parents[1]
    command_blob = base64.b64encode(
        json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    runner_invocation = (
        f"{shlex.quote(python_executable)} -m agent_workflow.runner "
        f"--run-dir {shlex.quote(str(state_dir))} "
        f"--command-b64 {shlex.quote(command_blob)} "
        f"{'--interactive ' if interactive else ''}"
    )
    if interactive and not close_tmux_on_exit:
        runner_command = (
            "if [[ -t 0 ]]; then\n"
            f"    exec {runner_invocation}\n"
            "else\n"
            f"    exec {runner_invocation.replace('--interactive ', '', 1)}\n"
            "fi"
        )
    elif close_tmux_on_exit:
        fallback_invocation = runner_invocation.replace("--interactive ", "", 1)
        runner_command = (
            "if [[ -t 0 ]]; then\n"
            "    set +e\n"
            f"    {runner_invocation}\n"
            "    runner_status=$?\n"
            "    set -e\n"
            "    if [[ -n \"${AGENT_WORKFLOW_TMUX_SESSION:-}\" ]]; then\n"
            "        tmux kill-session -t \"$AGENT_WORKFLOW_TMUX_SESSION\" >/dev/null 2>&1 || true\n"
            "    fi\n"
            "    exit \"$runner_status\"\n"
            "else\n"
            f"    exec {fallback_invocation}\n"
            "fi"
        )
    else:
        runner_command = f"exec {runner_invocation}"
    runner_text = (
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        f"readonly AGENT_WORKFLOW_SESSION_ID={shlex.quote(session_id)}\n"
        f"readonly AGENT_WORKFLOW_PROMPT_SOURCE={shlex.quote(str(prompt_source))}\n"
        f"readonly AGENT_WORKFLOW_HANDOFF_DIR={shlex.quote(str(handoff_dir or ''))}\n"
        f"readonly AGENT_WORKFLOW_CONTROL_BRIDGE={shlex.quote(str((handoff_dir / 'control-intents') if handoff_dir else ''))}\n"
        f"readonly AGENT_WORKFLOW_COMPLETION_TEMPLATE={shlex.quote(str(completion_template_path or ''))}\n"
        f"readonly AGENT_WORKFLOW_PROMPT_PACK_ROOT={shlex.quote(str(prompt_pack_root or ''))}\n"
        f"readonly AGENT_WORKFLOW_COMMAND_CATALOG={shlex.quote(str(state_dir / str((command_artifacts or {}).get('catalog_path', 'command-catalog.json'))))}\n"
        f"readonly AGENT_WORKFLOW_COMMAND_CARD={shlex.quote(str(state_dir / str((command_artifacts or {}).get('card_path', 'command-card.md'))))}\n"
        f"readonly AGENT_WORKFLOW_CLI={shlex.quote(str(((command_artifacts or {}).get('cli_invocation') or ['agent-workflow'])[0]))}\n"
    )
    if close_tmux_on_exit:
        runner_text += (
            f"readonly AGENT_WORKFLOW_TMUX_SESSION={shlex.quote(session_id)}\n"
        )
    runner_text += (
        "export AGENT_WORKFLOW_SESSION_ID AGENT_WORKFLOW_PROMPT_SOURCE "
        "AGENT_WORKFLOW_HANDOFF_DIR AGENT_WORKFLOW_PROMPT_PACK_ROOT "
        "AGENT_WORKFLOW_CONTROL_BRIDGE "
        "AGENT_WORKFLOW_COMPLETION_TEMPLATE AGENT_WORKFLOW_COMMAND_CATALOG "
        "AGENT_WORKFLOW_COMMAND_CARD AGENT_WORKFLOW_CLI"
        + (" AGENT_WORKFLOW_TMUX_SESSION\n" if close_tmux_on_exit else "\n")
        + f"export PYTHONPATH={shlex.quote(str(source_root))}${{PYTHONPATH:+:$PYTHONPATH}}\n"
        + runner_command
        + "\n"
    )
    runner.write_text(runner_text, encoding="utf-8")
    runner.chmod(0o755)
    syntax = run(
        ["bash", "-n", str(runner)],
        check=False,
        timeout_seconds=10,
        max_stdout_bytes=64 * 1024,
        max_stderr_bytes=64 * 1024,
    )
    if syntax.returncode:
        raise WorkflowError(
            f"generated runner failed syntax check: {syntax.stderr.strip()}"
        )
    return runner


def _discover_prompt_pack_root(prompt_source: Path) -> Path | None:
    for candidate in prompt_source.parents:
        try:
            read_regular_file(candidate / "pack.yaml")
        except WorkflowError:
            continue
        else:
            return candidate
    return None


def _pack_id(pack_root: Path) -> str:
    """Read the deliberately small, stable identity field from pack.yaml."""
    pack_file = pack_root / "pack.yaml"
    try:
        for line in read_regular_file(pack_file).data.decode("utf-8").splitlines():
            key, separator, value = line.partition(":")
            if key.strip() == "pack_id" and separator and value.strip():
                return value.strip().strip("\"'")
    except OSError as exc:
        raise WorkflowError(f"cannot read selected pack: {pack_file}: {exc}") from exc
    raise WorkflowError(f"selected pack has no pack_id: {pack_file}")
