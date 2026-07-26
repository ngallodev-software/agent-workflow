from __future__ import annotations
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from .errors import WorkflowError
from .util import expand_path


@dataclass(frozen=True)
class ExecutorPolicy:
    interactive_command: list[str] = field(default_factory=list)
    models: tuple[str, ...] = ()
    default_model: str | None = None
    no_go_models: tuple[str, ...] = ()
    model_arg: tuple[str, ...] = ("--model",)
    interactive_permission_args: tuple[str, ...] = ()
    non_interactive_permission_args: tuple[str, ...] = ()
    environment_allowlist: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentProfile:
    executor: str | None = None
    model: str | None = None
    allow_no_go_model: bool = False
    interactive: bool | None = None
    agent_class: str | None = None


@dataclass(frozen=True)
class AgentClassPolicy:
    interactive: bool
    default_executor: str
    default_model: str
    allowed_models: dict[str, tuple[str, ...]] = field(default_factory=dict)


def _xdg(name: str, fallback: str) -> Path:
    return expand_path(os.environ.get(name, fallback))


@dataclass(frozen=True)
class Settings:
    config_path: Path
    worktree_root: Path
    state_root: Path
    terminal_backend: str = "tmux"
    stall_minutes: int = 10
    capture_lines: int = 50
    mouse: bool = True
    orchestrator_side: str = "left"
    max_interactive_agent_width: int = 2
    max_interactive_agent_vertical: int = 3
    branch_prefix: str = "impl/"
    require_clean_source: bool = True
    archive_level: int = 19
    write_sha256: bool = True
    validate_before_archive: bool = True
    executors: dict[str, list[str]] = field(default_factory=dict)
    executor_policies: dict[str, ExecutorPolicy] = field(default_factory=dict)
    preferred_agent_names: tuple[str, ...] = ()
    generated_agent_prefix: str = "agent"
    default_agent_executor: str = "codex"
    agent_profiles: dict[str, AgentProfile] = field(default_factory=dict)
    non_interactive_tmux: str = "dedicated_session"
    default_agent_class: str = "implementation"
    agent_classes: dict[str, AgentClassPolicy] = field(default_factory=dict)
    reuse_stale_minutes: int = 120

    @property
    def max_interactive_agent_panes(self) -> int:
        return self.max_interactive_agent_width * self.max_interactive_agent_vertical


def default_config_path() -> Path:
    return _xdg("XDG_CONFIG_HOME", "~/.config") / "agent-workflow" / "config.toml"


def defaults(path: Path | None = None) -> Settings:
    return Settings(
        config_path=path or default_config_path(),
        worktree_root=_xdg("XDG_DATA_HOME", "~/.local/share")
        / "agent-workflow"
        / "worktrees",
        state_root=_xdg("XDG_STATE_HOME", "~/.local/state") / "agent-workflow",
        executors={
            "codex": [
                "codex",
                "exec",
                "--sandbox",
                "workspace-write",
                "--skip-git-repo-check",
                "-",
            ],
            "claude": ["claude", "--print"],
        },
        executor_policies={
            "codex": ExecutorPolicy(
                interactive_command=["codex"],
                models=("gpt-5.4-mini", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"),
                default_model="gpt-5.4-mini",
                no_go_models=("gpt-5.6-sol", "*fast*"),
                interactive_permission_args=("--ask-for-approval", "on-request"),
            ),
            "claude": ExecutorPolicy(
                interactive_command=["claude"],
                models=("haiku", "sonnet", "opus", "fable"),
                default_model="sonnet",
                no_go_models=("opus", "fable"),
                interactive_permission_args=("--permission-mode", "manual"),
                non_interactive_permission_args=("--permission-mode", "manual"),
            ),
        },
        agent_classes={
            "exploratory": AgentClassPolicy(
                interactive=False,
                default_executor="claude",
                default_model="haiku",
                allowed_models={"claude": ("haiku",), "codex": ("gpt-5.4-mini",)},
            ),
            "review": AgentClassPolicy(
                interactive=False,
                default_executor="codex",
                default_model="gpt-5.4-mini",
                allowed_models={
                    "claude": ("haiku", "sonnet"),
                    "codex": ("gpt-5.4-mini", "gpt-5.6-luna"),
                },
            ),
            "implementation": AgentClassPolicy(
                interactive=True,
                default_executor="codex",
                default_model="gpt-5.4-mini",
                allowed_models={
                    "claude": ("haiku", "sonnet"),
                    "codex": ("gpt-5.4-mini", "gpt-5.6-luna", "gpt-5.6-terra"),
                },
            ),
        },
    )


def _nested(data: dict[str, Any], section: str, key: str, default: Any) -> Any:
    table = data.get(section, {})
    if not isinstance(table, dict):
        raise WorkflowError(f"config section [{section}] must be a table")
    return table.get(key, default)


def _integer(data: dict[str, Any], section: str, key: str, default: int) -> int:
    value = _nested(data, section, key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkflowError(f"config value [{section}].{key} must be an integer")
    return value


def _boolean(data: dict[str, Any], section: str, key: str, default: bool) -> bool:
    value = _nested(data, section, key, default)
    if not isinstance(value, bool):
        raise WorkflowError(f"config value [{section}].{key} must be a boolean")
    return value


def _choice(data: dict[str, Any], section: str, key: str, default: str, choices: set[str]) -> str:
    value = _nested(data, section, key, default)
    if not isinstance(value, str) or value not in choices:
        raise WorkflowError(
            f"config value [{section}].{key} must be one of: {', '.join(sorted(choices))}"
        )
    return value


def load_settings(path: Path | None = None) -> Settings:
    path = expand_path(path or default_config_path())
    base = defaults(path)
    if not path.exists():
        return base
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise WorkflowError(f"cannot read config {path}: {exc}") from exc
    executors = dict(base.executors)
    policies = dict(base.executor_policies)
    raw = data.get("executors", {})
    if not isinstance(raw, dict):
        raise WorkflowError("[executors] must contain executor tables")
    for name, entry in raw.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("command"), list):
            raise WorkflowError(f"executor {name!r} requires command = [..]")
        command = entry["command"]
        if not command or not all(isinstance(x, str) and x for x in command):
            raise WorkflowError(
                f"executor {name!r} command must be a non-empty string list"
            )
        executors[name] = command
        def strings(key: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
            value = entry.get(key, list(default))
            if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
                raise WorkflowError(f"executor {name!r} {key} must be a string list")
            return tuple(value)
        prior = policies.get(name, ExecutorPolicy())
        interactive_command = list(strings("interactive_command", tuple(prior.interactive_command)))
        models = strings("models", prior.models)
        default_model = entry.get("default_model", prior.default_model)
        if default_model is not None and not isinstance(default_model, str):
            raise WorkflowError(f"executor {name!r} default_model must be a string")
        if models and default_model not in models:
            raise WorkflowError(f"executor {name!r} default_model must be listed in models")
        legacy_permission_args = strings("permission_args") if "permission_args" in entry else ()
        policies[name] = ExecutorPolicy(
            interactive_command=interactive_command,
            models=models,
            default_model=default_model,
            no_go_models=strings("no_go_models", prior.no_go_models),
            model_arg=strings("model_arg", prior.model_arg),
            interactive_permission_args=strings(
                "interactive_permission_args",
                legacy_permission_args or prior.interactive_permission_args,
            ),
            non_interactive_permission_args=strings(
                "non_interactive_permission_args",
                legacy_permission_args or prior.non_interactive_permission_args,
            ),
            environment_allowlist=strings(
                "environment_allowlist", prior.environment_allowlist
            ),
        )
    stall = _integer(data, "terminal", "stall_minutes", base.stall_minutes)
    capture = _integer(data, "terminal", "capture_lines", base.capture_lines)
    max_interactive_width = _integer(
        data,
        "terminal",
        "max_interactive_agent_width",
        base.max_interactive_agent_width,
    )
    max_interactive_vertical = _integer(
        data,
        "terminal",
        "max_interactive_agent_vertical",
        base.max_interactive_agent_vertical,
    )
    level = _integer(data, "pack", "archive_level", base.archive_level)
    reuse_stale = _integer(
        data, "agents", "reuse_stale_minutes", base.reuse_stale_minutes
    )
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        raise WorkflowError("[agents] must be a table")
    preferred_names = agents.get("preferred_names", list(base.preferred_agent_names))
    if not isinstance(preferred_names, list) or not all(
        isinstance(value, str) and value for value in preferred_names
    ):
        raise WorkflowError("[agents].preferred_names must be a string list")
    if len(preferred_names) != len(set(preferred_names)):
        raise WorkflowError("[agents].preferred_names must not contain duplicates")
    generated_prefix = agents.get("generated_prefix", base.generated_agent_prefix)
    default_executor = agents.get("default_executor", base.default_agent_executor)
    default_agent_class = agents.get("default_class", base.default_agent_class)
    if not isinstance(generated_prefix, str) or not generated_prefix:
        raise WorkflowError("[agents].generated_prefix must be a non-empty string")
    if not isinstance(default_executor, str) or default_executor not in executors:
        raise WorkflowError("[agents].default_executor must name a configured executor")
    raw_classes = data.get("agent_classes", {})
    if not isinstance(raw_classes, dict):
        raise WorkflowError("[agent_classes] must contain class tables")
    classes = dict(base.agent_classes)
    for class_name, class_data in raw_classes.items():
        if not isinstance(class_data, dict):
            raise WorkflowError(f"agent class {class_name!r} must be a table")
        class_interactive = class_data.get("interactive")
        class_executor = class_data.get("default_executor")
        class_model = class_data.get("default_model")
        class_models = class_data.get("models", {})
        if not isinstance(class_interactive, bool):
            raise WorkflowError(f"agent class {class_name!r} interactive must be boolean")
        if not isinstance(class_executor, str) or class_executor not in executors:
            raise WorkflowError(f"agent class {class_name!r} default_executor is not configured")
        if not isinstance(class_model, str) or not class_model:
            raise WorkflowError(f"agent class {class_name!r} default_model must be a string")
        if not isinstance(class_models, dict):
            raise WorkflowError(f"agent class {class_name!r} models must be a table")
        allowed_models: dict[str, tuple[str, ...]] = {}
        for class_executor_name, class_model_list in class_models.items():
            if class_executor_name not in executors or not isinstance(class_model_list, list) or not all(
                isinstance(value, str) and value for value in class_model_list
            ):
                raise WorkflowError(f"agent class {class_name!r} has invalid models for {class_executor_name!r}")
            allowed_models[class_executor_name] = tuple(class_model_list)
        if class_model not in allowed_models.get(class_executor, ()):
            raise WorkflowError(f"agent class {class_name!r} default model is not allowed")
        classes[class_name] = AgentClassPolicy(
            class_interactive, class_executor, class_model, allowed_models
        )
    if not isinstance(default_agent_class, str) or default_agent_class not in classes:
        raise WorkflowError("[agents].default_class must name a configured agent class")
    raw_profiles = agents.get("profiles", {})
    if not isinstance(raw_profiles, dict):
        raise WorkflowError("[agents.profiles] must contain profile tables")
    profiles: dict[str, AgentProfile] = {}
    for agent_name, profile in raw_profiles.items():
        if not isinstance(profile, dict):
            raise WorkflowError(f"agent profile {agent_name!r} must be a table")
        profile_executor = profile.get("executor")
        profile_model = profile.get("model")
        profile_allow_no_go = profile.get("allow_no_go_model", False)
        profile_interactive = profile.get("interactive")
        profile_class = profile.get("class")
        if not isinstance(profile_executor, str) or profile_executor not in executors:
            raise WorkflowError(f"agent profile {agent_name!r} executor is not configured")
        if not isinstance(profile_model, str) or not profile_model:
            raise WorkflowError(f"agent profile {agent_name!r} model must be a string")
        if not isinstance(profile_allow_no_go, bool):
            raise WorkflowError(f"agent profile {agent_name!r} allow_no_go_model must be boolean")
        if profile_interactive is not None and not isinstance(profile_interactive, bool):
            raise WorkflowError(f"agent profile {agent_name!r} interactive must be boolean")
        if profile_class is not None and (
            not isinstance(profile_class, str) or profile_class not in classes
        ):
            raise WorkflowError(f"agent profile {agent_name!r} class is not configured")
        profiles[agent_name] = AgentProfile(
            profile_executor,
            profile_model,
            profile_allow_no_go,
            profile_interactive,
            profile_class,
        )
    unknown_profiles = set(profiles) - set(preferred_names)
    if unknown_profiles:
        raise WorkflowError(
            "agent profiles must be listed in preferred_names: " + ", ".join(sorted(unknown_profiles))
        )
    if (
        stall < 1
        or capture < 1
        or max_interactive_width < 1
        or max_interactive_vertical < 1
        or reuse_stale < 1
        or not 1 <= level <= 22
    ):
        raise WorkflowError("invalid stall_minutes, capture_lines, or archive_level")
    return Settings(
        config_path=path,
        worktree_root=expand_path(
            _nested(data, "paths", "worktree_root", base.worktree_root)
        ),
        state_root=expand_path(_nested(data, "paths", "state_root", base.state_root)),
        terminal_backend=str(
            _nested(data, "terminal", "backend", base.terminal_backend)
        ),
        stall_minutes=stall,
        capture_lines=capture,
        mouse=_boolean(data, "terminal", "mouse", base.mouse),
        orchestrator_side=_choice(
            data, "terminal", "orchestrator_side", base.orchestrator_side, {"left", "right"}
        ),
        max_interactive_agent_width=max_interactive_width,
        max_interactive_agent_vertical=max_interactive_vertical,
        branch_prefix=str(_nested(data, "git", "branch_prefix", base.branch_prefix)),
        require_clean_source=_boolean(
            data, "git", "require_clean_source", base.require_clean_source
        ),
        archive_level=level,
        write_sha256=_boolean(data, "pack", "write_sha256", base.write_sha256),
        validate_before_archive=_boolean(
            data, "pack", "validate_before_archive", base.validate_before_archive
        ),
        executors=executors,
        executor_policies=policies,
        preferred_agent_names=tuple(preferred_names),
        generated_agent_prefix=generated_prefix,
        default_agent_executor=default_executor,
        agent_profiles=profiles,
        non_interactive_tmux=_choice(
            data,
            "agents",
            "non_interactive_tmux",
            base.non_interactive_tmux,
            {"dedicated_session", "shared_window"},
        ),
        default_agent_class=default_agent_class,
        agent_classes=classes,
        reuse_stale_minutes=reuse_stale,
    )


def as_dict(s: Settings) -> dict[str, Any]:
    return {
        "config_path": str(s.config_path),
        "paths": {
            "worktree_root": str(s.worktree_root),
            "state_root": str(s.state_root),
        },
        "terminal": {
            "backend": s.terminal_backend,
            "stall_minutes": s.stall_minutes,
            "capture_lines": s.capture_lines,
            "mouse": s.mouse,
            "orchestrator_side": s.orchestrator_side,
            "max_interactive_agent_width": s.max_interactive_agent_width,
            "max_interactive_agent_vertical": s.max_interactive_agent_vertical,
            "max_interactive_agent_panes": s.max_interactive_agent_panes,
        },
        "git": {
            "branch_prefix": s.branch_prefix,
            "require_clean_source": s.require_clean_source,
        },
        "pack": {
            "archive_level": s.archive_level,
            "write_sha256": s.write_sha256,
            "validate_before_archive": s.validate_before_archive,
        },
        "executors": {
            name: {
                "command": command,
                "interactive_command": s.executor_policies.get(name, ExecutorPolicy()).interactive_command,
                "models": list(s.executor_policies.get(name, ExecutorPolicy()).models),
                "default_model": s.executor_policies.get(name, ExecutorPolicy()).default_model,
                "no_go_models": list(s.executor_policies.get(name, ExecutorPolicy()).no_go_models),
                "model_arg": list(s.executor_policies.get(name, ExecutorPolicy()).model_arg),
                "interactive_permission_args": list(
                    s.executor_policies.get(name, ExecutorPolicy()).interactive_permission_args
                ),
                "non_interactive_permission_args": list(
                    s.executor_policies.get(name, ExecutorPolicy()).non_interactive_permission_args
                ),
                "environment_allowlist": list(
                    s.executor_policies.get(name, ExecutorPolicy()).environment_allowlist
                ),
            }
            for name, command in s.executors.items()
        },
        "agents": {
            "preferred_names": list(s.preferred_agent_names),
            "generated_prefix": s.generated_agent_prefix,
            "default_executor": s.default_agent_executor,
            "profiles": {
                name: {
                    "executor": profile.executor,
                    "model": profile.model,
                    "allow_no_go_model": profile.allow_no_go_model,
                    "interactive": profile.interactive,
                    "class": profile.agent_class,
                }
                for name, profile in sorted(s.agent_profiles.items())
            },
            "non_interactive_tmux": s.non_interactive_tmux,
            "default_class": s.default_agent_class,
            "reuse_stale_minutes": s.reuse_stale_minutes,
        },
        "agent_classes": {
            name: {
                "interactive": policy.interactive,
                "default_executor": policy.default_executor,
                "default_model": policy.default_model,
                "models": {executor: list(models) for executor, models in policy.allowed_models.items()},
            }
            for name, policy in sorted(s.agent_classes.items())
        },
    }
