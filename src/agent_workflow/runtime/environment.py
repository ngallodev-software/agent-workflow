"""Controlled child-environment policy for bounded process execution."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..errors import WorkflowError

DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


@dataclass(frozen=True)
class EnvironmentPolicy:
    """Explicit child environment policy.

    Values in ``values`` are caller-supplied named values. Ambient values are
    copied only when their names appear in ``allowlist``. ``unsafe_inherit``
    is intentionally explicit and is recorded in the result; governed launch
    paths do not use it.
    """

    allowlist: tuple[str, ...] = (
        "FAKE_AGENT_MODE",
        "FAKE_AGENT_DELAY",
        "FAKE_AGENT_RESULT_JSON",
        "FAKE_AGENT_AUTO_STEER",
        "FAKE_AGENT_EMPTY_COMPLETION",
        "FAKE_AGENT_STEER_OUTCOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    )
    values: Mapping[str, str] = field(default_factory=dict)
    unsafe_inherit: bool = False
    git_config_policy: str = "isolated"


def _controlled_path(resolved: str | None) -> str:
    directories = DEFAULT_PATH.split(os.pathsep)
    if resolved:
        parent = str(Path(resolved).parent)
        if parent not in directories:
            directories.insert(0, parent)
    return os.pathsep.join(directories)


def build_environment(
    command: Sequence[str], policy: EnvironmentPolicy
) -> tuple[dict[str, str], str, tuple[str, ...]]:
    resolved = shutil.which(command[0], path=os.environ.get("PATH", DEFAULT_PATH))
    environment: dict[str, str] = {
        "PATH": _controlled_path(resolved),
        "LC_ALL": "C",
        "LANG": "C",
        "LANGUAGE": "C",
        "TZ": "UTC",
    }
    if policy.unsafe_inherit:
        environment.update({str(key): str(value) for key, value in os.environ.items()})
        environment["PATH"] = _controlled_path(resolved)
    else:
        for name in policy.allowlist:
            if name in os.environ:
                environment[name] = os.environ[name]
    for name, value in policy.values.items():
        if not isinstance(name, str) or not name or "=" in name or "\x00" in name:
            raise WorkflowError(f"invalid environment variable name: {name!r}")
        environment[name] = str(value)

    # Git is a policy input boundary. Pagers, external diff helpers, editors,
    # and prompts are always disabled. Governed commands isolate system/global
    # config by default, while an explicit operator policy preserves the same
    # excludes/config inputs used by a human ``git status`` cleanliness check.
    if Path(command[0]).name == "git":
        if policy.git_config_policy not in {"isolated", "operator"}:
            raise WorkflowError("git_config_policy must be isolated or operator")
        if policy.git_config_policy == "isolated":
            environment.update(
                {
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_SYSTEM": os.devnull,
                    "GIT_CONFIG_GLOBAL": os.devnull,
                }
            )
        else:
            for name in ("GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_GLOBAL"):
                if name not in policy.values:
                    environment.pop(name, None)
        environment.update(
            {
                "GIT_PAGER": "cat",
                "PAGER": "cat",
                "GIT_EXTERNAL_DIFF": "",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_EDITOR": "true",
                "GIT_SEQUENCE_EDITOR": "true",
                "GIT_ASKPASS": "true",
                "SSH_ASKPASS": "true",
            }
        )
    policy_name = "unsafe-inherit" if policy.unsafe_inherit else "controlled"
    if Path(command[0]).name == "git" and policy.git_config_policy == "operator":
        policy_name += "+operator-git-config"
    return environment, policy_name, tuple(str(value) for value in policy.values.values())
