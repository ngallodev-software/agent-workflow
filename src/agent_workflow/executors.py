from __future__ import annotations

import json
import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import LUNA_MODEL, LUNA_REASONING_EFFORTS, Settings
from .errors import WorkflowError
from .process import ExecutableIdentity, executor_identity

StreamFormat = str


@dataclass(frozen=True)
class ExecutorPlan:
    name: str | None
    argv: tuple[str, ...]
    stream_format: StreamFormat = "text"
    model: str | None = None
    no_go_authorized: bool = False
    reasoning_effort: str | None = None


def _insert_before_stdin(argv: list[str], values: list[str]) -> list[str]:
    if "-" in argv:
        index = len(argv) - 1 - argv[::-1].index("-")
        return argv[:index] + values + argv[index:]
    return argv + values


def _infer_executor(argv: list[str]) -> str | None:
    """Identify supported executors from an explicit command's executable."""
    if not argv:
        return None
    executable = Path(argv[0]).name.lower()
    if executable == "codex":
        return "codex"
    if executable in {"claude", "claude-code"}:
        return "claude"
    return None


def _explicit_model(argv: list[str]) -> str | None:
    for index, value in enumerate(argv):
        if value in {"--model", "-m"} and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith("--model="):
            return value.split("=", 1)[1]
        if value in {"-c", "--config"} and index + 1 < len(argv):
            setting = argv[index + 1]
            if setting.startswith("model="):
                return setting.split("=", 1)[1].strip('"')
    return None


def _explicit_reasoning_effort(argv: list[str]) -> str | None:
    for index, value in enumerate(argv):
        if value in {"-c", "--config"} and index + 1 < len(argv):
            setting = argv[index + 1]
            if setting.startswith("model_reasoning_effort="):
                return setting.split("=", 1)[1].strip('"')
        if value.startswith(("-c", "--config=")):
            setting = value.split("=", 1)[1] if "=" in value else ""
            if setting.startswith("model_reasoning_effort="):
                return setting.split("=", 1)[1].strip('"')
    return None


def _select_model(settings: Settings, executor: str | None, requested: str | None, allow_no_go: bool) -> tuple[str | None, bool]:
    if executor is None:
        if requested is not None:
            raise WorkflowError("--model requires a known configured executor")
        return None, False
    policy = settings.executor_policies.get(executor)
    selected = requested or (policy.default_model if policy else None)
    if selected is None:
        return None, False
    if policy and policy.models and selected not in policy.models:
        raise WorkflowError(f"model {selected!r} is not allowed for executor {executor!r}")
    no_go = bool(policy and any(fnmatch.fnmatchcase(selected, pattern) for pattern in policy.no_go_models))
    if no_go and not allow_no_go:
        raise WorkflowError(
            f"model {selected!r} is no-go for executor {executor!r}; "
            "pass --allow-no-go-model to record explicit permission"
        )
    return selected, no_go and allow_no_go


def _select_reasoning_effort(
    settings: Settings,
    executor: str | None,
    requested: str | None,
    explicit: str | None,
) -> str | None:
    if executor != "codex":
        if requested is not None:
            raise WorkflowError("reasoning effort is supported only for Codex")
        return None
    selected = requested or explicit or settings.executor_policies[executor].reasoning_effort
    if selected not in LUNA_REASONING_EFFORTS:
        raise WorkflowError(
            "Codex reasoning effort must be one of: low, medium, high"
        )
    if requested is not None and explicit is not None and requested != explicit:
        raise WorkflowError("reasoning effort disagrees with the explicit Codex command")
    return selected


def prepare_executor(
    settings: Settings,
    executor: str | None,
    explicit: list[str] | None,
    *,
    structured: bool = False,
    interactive: bool = False,
    model: str | None = None,
    reasoning_effort: str | None = None,
    allow_no_go_model: bool = False,
) -> ExecutorPlan:
    if structured and interactive:
        raise WorkflowError("--structured and --interactive are mutually exclusive")
    if explicit:
        executor = _infer_executor(explicit)
        argv = list(explicit)
        explicit_model = _explicit_model(argv)
        explicit_effort = _explicit_reasoning_effort(argv)
        if model and explicit_model and model != explicit_model:
            raise WorkflowError("--model disagrees with the explicit executor command")
        selected_model, authorized = _select_model(
            settings, executor, model or explicit_model, allow_no_go_model
        )
        if executor == "codex" and selected_model != LUNA_MODEL:
            raise WorkflowError("automatic Codex selection requires gpt-5.6-luna")
        selected_effort = _select_reasoning_effort(
            settings, executor, reasoning_effort, explicit_effort
        )
        policy = settings.executor_policies.get(executor) if executor else None
        if interactive and executor is not None:
            argv = list(policy.interactive_command if policy and policy.interactive_command else [argv[0]])
            argv.extend(policy.interactive_permission_args if policy else ())
        # Interactive execution rebuilds argv from the configured interactive
        # command, so model/effort supplied to the original explicit command
        # must be reinserted into that new command.
        if selected_model and (explicit_model is None or interactive):
            argv = _insert_before_stdin(argv, list(policy.model_arg) + [selected_model] if policy else ["--model", selected_model])
        if selected_effort and (explicit_effort is None or interactive):
            argv = _insert_before_stdin(argv, ["-c", f"model_reasoning_effort={selected_effort}"])
        stream_format = "text"
        if structured and executor == "codex":
            if "--json" not in argv:
                argv = _insert_before_stdin(argv, ["--json"])
            stream_format = "codex-jsonl"
        elif structured and executor == "claude":
            if "--print" in argv and "--verbose" not in argv:
                argv.append("--verbose")
            if "--output-format" not in argv:
                argv.extend(["--output-format", "stream-json"])
            stream_format = "claude-stream-json"
        return ExecutorPlan(executor, tuple(argv), stream_format, selected_model, authorized, selected_effort)
    if not executor:
        raise WorkflowError(
            "provide --executor NAME or an explicit command after --"
        )
    try:
        argv = list(settings.executors[executor])
    except KeyError as exc:
        known = ", ".join(sorted(settings.executors)) or "none"
        raise WorkflowError(
            f"unknown executor {executor!r}; configured executors: {known}"
        ) from exc
    if not argv:
        raise WorkflowError(f"executor {executor!r} has an empty command")
    policy = settings.executor_policies.get(executor)
    configured_model = _explicit_model(argv)
    if model and configured_model and model != configured_model:
        raise WorkflowError("--model disagrees with the configured executor command")
    selected_model, authorized = _select_model(
        settings, executor, model or configured_model, allow_no_go_model
    )
    if executor == "codex" and selected_model != LUNA_MODEL:
        raise WorkflowError("automatic Codex selection requires gpt-5.6-luna")
    selected_effort = _select_reasoning_effort(
        settings, executor, reasoning_effort, _explicit_reasoning_effort(argv)
    )
    if interactive and executor in {"codex", "claude"}:
        # Built-in policies provide the provider-specific interactive flags, but
        # a configured command may intentionally be a test double or wrapper.
        # Do not replace that command with the default provider binary.
        configured_executable = Path(argv[0]).name
        policy_executable = (
            Path(policy.interactive_command[0]).name
            if policy and policy.interactive_command
            else None
        )
        if policy and policy.interactive_command and configured_executable == policy_executable:
            argv = list(policy.interactive_command)
        argv.extend(policy.interactive_permission_args if policy else ())
        if selected_model:
            argv.extend(list(policy.model_arg) + [selected_model] if policy else ["--model", selected_model])
        if selected_effort and _explicit_reasoning_effort(argv) is None:
            argv.extend(["-c", f"model_reasoning_effort={selected_effort}"])
        return ExecutorPlan(executor, tuple(argv), "text", selected_model, authorized, selected_effort)
    if policy:
        argv = _insert_before_stdin(argv, list(policy.non_interactive_permission_args))
    if selected_model:
        argv = _insert_before_stdin(argv, list(policy.model_arg) + [selected_model] if policy else ["--model", selected_model])
    if selected_effort and _explicit_reasoning_effort(argv) is None:
        argv = _insert_before_stdin(argv, ["-c", f"model_reasoning_effort={selected_effort}"])
    stream_format = "text"
    if executor == "codex" and "--skip-git-repo-check" not in argv:
        argv = _insert_before_stdin(argv, ["--skip-git-repo-check"])
    if structured and executor == "codex":
        if "--json" not in argv:
            argv = _insert_before_stdin(argv, ["--json"])
        stream_format = "codex-jsonl"
    elif structured and executor == "claude":
        if "--print" in argv and "--verbose" not in argv:
            argv.append("--verbose")
        if "--output-format" not in argv:
            argv.extend(["--output-format", "stream-json"])
        stream_format = "claude-stream-json"
    return ExecutorPlan(executor, tuple(argv), stream_format, selected_model, authorized, selected_effort)


def executor_version(plan: ExecutorPlan) -> str | None:
    return executor_identity(plan.argv).version


def executor_identity_for_plan(plan: ExecutorPlan) -> ExecutableIdentity:
    return executor_identity(plan.argv)


def parse_event(line: str, stream_format: StreamFormat) -> dict[str, Any] | None:
    if stream_format == "text":
        return None
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def event_text(event: dict[str, Any], stream_format: StreamFormat) -> list[str]:
    result: list[str] = []
    if stream_format == "codex-jsonl":
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str):
                result.append(text)
        message = event.get("message")
        if isinstance(message, str) and event.get("type") in {
            "error",
            "warning",
        }:
            result.append(message)
    elif stream_format == "claude-stream-json":
        message = event.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text")
                        if isinstance(text, str):
                            result.append(text)
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            result.append(str(event["result"]))
    return result


def event_usage(event: dict[str, Any]) -> dict[str, Any] | None:
    usage = event.get("usage")
    if isinstance(usage, dict):
        return dict(usage)
    item = event.get("item")
    if isinstance(item, dict) and isinstance(item.get("usage"), dict):
        return dict(item["usage"])
    return None


_USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "total_tokens",
    "cost",
)


def _usage_number(value: object) -> int | float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        return None
    return value


def accumulate_usage(
    current: dict[str, Any] | None,
    usage: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    """Merge an explicitly classified provider usage update.

    ``delta`` values are added; ``cumulative`` and ``terminal`` values replace
    only the fields they report.  Callers must classify the update--this helper
    intentionally does not guess from a provider's payload shape.
    """
    if mode not in {"delta", "cumulative", "terminal"}:
        raise ValueError(f"unsupported usage mode: {mode}")
    result = dict(current or {})
    aliases = {
        "input_tokens": ("input_tokens", "prompt_tokens"),
        "cached_input_tokens": (
            "cached_input_tokens",
            "cache_read_input_tokens",
            "cached_tokens",
        ),
        "output_tokens": ("output_tokens", "completion_tokens"),
        "total_tokens": ("total_tokens",),
        "cost": ("cost", "total_cost"),
    }
    details = usage.get("prompt_tokens_details")
    if not isinstance(details, dict):
        details = {}
    for target, names in aliases.items():
        value = next((usage[name] for name in names if name in usage), None)
        if target == "cached_input_tokens" and value is None:
            value = details.get("cached_tokens")
        number = _usage_number(value)
        if number is None:
            continue
        if mode == "delta":
            result[target] = (_usage_number(result.get(target)) or 0) + number
        else:
            result[target] = number
    currency = usage.get("currency")
    if isinstance(currency, str) and currency:
        result["currency"] = currency
    return result


def usage_update(event: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    """Return a usage payload plus its explicit update mode, if available."""
    usage = event_usage(event)
    if usage is None:
        return None
    mode = usage.pop("mode", event.get("usage_mode", event.get("usage_type", None)))
    if mode in {"delta", "cumulative", "terminal"}:
        return usage, mode
    # Compatibility boundary: legacy adapters expose only a final usage object.
    # A provider that streams interim usage must label those updates explicitly.
    return usage, "terminal"
