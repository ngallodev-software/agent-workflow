from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .errors import WorkflowError

CODEX_VERSION = "0.144.5"
CLAUDE_VERSION = "2.1.212"


def _load_inspect_api() -> tuple[Any, ...]:
    try:
        from inspect_ai import Task, eval as inspect_eval
        from inspect_ai.dataset import Sample
        from inspect_ai.util import SandboxEnvironmentSpec
        from inspect_swe import claude_code, codex_cli
    except ModuleNotFoundError as exc:
        raise WorkflowError(
            "Inspect support requires: pip install 'agent-workflow[eval]'"
        ) from exc
    return inspect_eval, Task, Sample, SandboxEnvironmentSpec, codex_cli, claude_code


def build_task(
    *,
    prompt: str,
    executor: Literal["codex", "claude"],
    sample_id: str,
    dockerfile: Path,
    setup: str | None = None,
    files: dict[str, str] | None = None,
) -> Any:
    _, Task, Sample, SandboxEnvironmentSpec, codex_cli, claude_code = (
        _load_inspect_api()
    )
    if executor == "codex":
        agent = codex_cli(
            cwd="/workspace",
            version=CODEX_VERSION,
            attempts=1,
            retry_refusals=0,
            web_search="disabled",
        )
    else:
        agent = claude_code(
            cwd="/workspace",
            version=CLAUDE_VERSION,
            attempts=1,
            retry_refusals=0,
            retry_uncaught_errors=0,
        )
    sample = Sample(
        id=sample_id,
        input=prompt,
        files=files,
        setup=setup,
    )
    return Task(
        dataset=[sample],
        solver=agent,
        sandbox=SandboxEnvironmentSpec("docker", str(dockerfile.resolve())),
    )


def run_inspect(
    task: Any,
    *,
    model: str,
    log_dir: Path,
) -> list[dict[str, str | None]]:
    inspect_eval, *_ = _load_inspect_api()
    log_dir.mkdir(parents=True, exist_ok=True)
    logs = inspect_eval(
        task,
        model=model,
        log_dir=str(log_dir),
        sandbox_cleanup=True,
        fail_on_error=True,
        retry_on_error=0,
    )
    return [
        {
            "location": str(getattr(log, "location", "")) or None,
            "status": str(getattr(getattr(log, "status", None), "value", ""))
            or None,
        }
        for log in logs
    ]
