"""Agent naming plus logical-role/private-runtime resolution.

Agent-facing callers select a logical role.  Provider/model resolution stays
private to Agent-Workflow.  The legacy class/executor/model path remains only
as a compatibility/operator escape hatch during the 0.9 migration.
"""

from __future__ import annotations

import fcntl
import json
import os
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .roles import load_roles
from .run_lifecycle import authoritative_execution_status
from .state import TERMINAL_STATUSES, list_statuses, read_status, run_dir
from .util import atomic_write_json, utc_now, validate_id


@dataclass(frozen=True, slots=True)
class ResolvedAgentIdentity:
    agent_name: str
    agent_class: str
    role_id: str
    role_digest: str
    role_instructions: str | None
    command_profile: str
    runtime_alias: str | None
    executor: str | None
    model: str | None
    reasoning_effort: str | None
    allow_no_go_model: bool
    interactive: bool


def status_agent_active(settings: Settings, item: dict[str, Any]) -> bool:
    """Return whether an Agent Run still owns or awaits a worker."""
    agent_run_id = item.get("agent_run_id")
    if not isinstance(agent_run_id, str) or not agent_run_id:
        return True
    try:
        status = authoritative_execution_status(run_dir(settings, agent_run_id))
    except WorkflowError:
        return True
    if status in TERMINAL_STATUSES:
        return False
    if status == "prepared":
        return True
    worker_alive = item.get("worker_alive")
    return worker_alive is not False


def _compat_class_for_role(settings: Settings, role_id: str) -> str:
    if role_id == "review":
        candidate = "review"
    elif role_id == "exploration":
        candidate = "exploratory"
    elif role_id in settings.agent_classes:
        candidate = role_id
    else:
        candidate = "implementation"
    if candidate not in settings.agent_classes:
        raise WorkflowError(f"logical role {role_id!r} has no compatible agent class")
    return candidate


def _role_for_legacy_class(agent_class: str) -> str:
    value = agent_class.strip().lower()
    if "review" in value or "gate" in value or "audit" in value:
        return "review"
    if "explor" in value or "research" in value or "discover" in value:
        return "exploration"
    return "implementation"


def resolve_agent_identity(
    settings: Settings,
    *,
    requested_name: str | None,
    requested_role: str | None,
    requested_class: str | None,
    executor: str | None,
    model: str | None,
    allow_no_go_model: bool,
    explicit_command: list[str] | None,
    interactive: bool | None,
    reasoning_effort: str | None = None,
    allow_active_name: bool = False,
) -> ResolvedAgentIdentity:
    """Resolve logical identity first, then private runtime selection.

    The role-first path is selected when ``--role`` is explicit or when the
    caller supplies no legacy runtime/class/profile override.  Low-level
    executor/model selection therefore remains available for maintainers and
    compatibility without becoming normal orchestration vocabulary.
    """
    interactive_explicit = interactive is not None
    active_names = {
        str(item["agent_name"])
        for item in list_statuses(settings)
        if item.get("agent_name") and status_agent_active(settings, item)
    }
    if requested_name is not None:
        validate_id(requested_name, "agent name")
        generated_name = requested_name.startswith(f"{settings.generated_agent_prefix}-")
        if requested_name not in settings.preferred_agent_names and not generated_name:
            raise WorkflowError(
                f"agent name {requested_name!r} is not listed in [agents].preferred_names"
            )
        if requested_name in active_names and not allow_active_name:
            raise WorkflowError(f"agent name is already active: {requested_name}")
        agent_name = requested_name
    else:
        agent_name = next(
            (name for name in settings.preferred_agent_names if name not in active_names),
            "",
        )
        if not agent_name:
            index = 1
            while f"{settings.generated_agent_prefix}-{index:02d}" in active_names:
                index += 1
            agent_name = f"{settings.generated_agent_prefix}-{index:02d}"

    profile = settings.agent_profiles.get(agent_name)
    explicit_role = requested_role is not None
    legacy_override = any(
        value is not None
        for value in (requested_class, executor, model, explicit_command)
    ) or allow_no_go_model or reasoning_effort is not None
    role_first = explicit_role or not legacy_override

    roles = load_roles(settings.role_paths)
    if role_first:
        if explicit_role and legacy_override:
            raise WorkflowError(
                "--role cannot be combined with --agent-class, --executor, --model, "
                "--reasoning-effort, --allow-no-go-model, or an explicit command"
            )
        role_id = requested_role or settings.default_agent_role
        role = roles.get(role_id)
        if role is None:
            raise WorkflowError(f"agent role is not configured: {role_id}")
        alias_name = settings.role_bindings.get(role_id)
        if not alias_name:
            raise WorkflowError(f"agent role has no private runtime binding: {role_id}")
        alias = settings.runtime_aliases.get(alias_name)
        if alias is None:
            raise WorkflowError(
                f"agent role {role_id!r} references unknown runtime alias {alias_name!r}"
            )
        agent_class = _compat_class_for_role(settings, role_id)
        class_policy = settings.agent_classes[agent_class]
        if interactive is None:
            interactive = class_policy.interactive
        if alias.executor == "claude" and not interactive_explicit:
            interactive = True
        return ResolvedAgentIdentity(
            agent_name=agent_name,
            agent_class=agent_class,
            role_id=role_id,
            role_digest=role.digest,
            role_instructions=role.instructions_markdown,
            command_profile=role.command_profile,
            runtime_alias=alias_name,
            executor=alias.executor,
            model=alias.model,
            reasoning_effort=alias.reasoning_effort,
            allow_no_go_model=False,
            interactive=bool(interactive),
        )

    # Legacy/operator compatibility path. Named profiles no longer select a
    # provider/model implicitly; they are consulted only after an explicit
    # low-level compatibility override selects this path.
    agent_class = requested_class or settings.default_agent_class
    if profile is not None:
        if explicit_command is not None and not allow_active_name:
            raise WorkflowError(f"agent profile {agent_name!r} cannot use an explicit command")
        if profile.agent_class is not None:
            if requested_class is not None and requested_class != profile.agent_class:
                raise WorkflowError(f"agent {agent_name!r} requires class {profile.agent_class!r}")
            agent_class = profile.agent_class
        if executor is not None and executor != profile.executor:
            raise WorkflowError(f"agent {agent_name!r} requires executor {profile.executor!r}")
        if model is not None and model != profile.model:
            raise WorkflowError(f"agent {agent_name!r} requires model {profile.model!r}")
        executor = profile.executor or executor
        model = profile.model or model
        allow_no_go_model = profile.allow_no_go_model
        if interactive is None and profile.interactive is not None:
            interactive = profile.interactive
    if agent_class not in settings.agent_classes:
        raise WorkflowError(f"agent class is not configured: {agent_class}")
    class_policy = settings.agent_classes[agent_class]
    if executor is None and explicit_command is None:
        executor = class_policy.default_executor or settings.default_agent_executor
    if model is None and executor is not None:
        if executor == class_policy.default_executor:
            model = class_policy.default_model
        else:
            allowed_for_executor = class_policy.allowed_models.get(executor, ())
            model = allowed_for_executor[0] if allowed_for_executor else None
    if executor is not None and model is not None:
        allowed_models = class_policy.allowed_models.get(executor, ())
        if model not in allowed_models:
            raise WorkflowError(
                f"agent class {agent_class!r} does not allow {executor}/{model}"
            )
    if interactive is None:
        interactive = class_policy.interactive
    if executor == "claude" and not interactive_explicit:
        interactive = True
    role_id = _role_for_legacy_class(agent_class)
    role = roles.get(role_id)
    if role is None:
        raise WorkflowError(f"compatibility role is not configured: {role_id}")
    return ResolvedAgentIdentity(
        agent_name=agent_name,
        agent_class=agent_class,
        role_id=role_id,
        role_digest=role.digest,
        role_instructions=role.instructions_markdown,
        command_profile=role.command_profile,
        runtime_alias=None,
        executor=executor,
        model=model,
        reasoning_effort=reasoning_effort,
        allow_no_go_model=allow_no_go_model,
        interactive=bool(interactive),
    )


def claim_agent_name(
    settings: Settings,
    *,
    agent_name: str,
    agent_run_id: str,
    interactive: bool,
) -> None:
    """Atomically reserve one name across interactive and detached runs."""
    lease_root = settings.state_root / "agent-name-leases"
    lease_root.mkdir(parents=True, exist_ok=True)
    lock_path = lease_root / ".lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        active_names = {
            str(item["agent_name"])
            for item in list_statuses(settings)
            if item.get("agent_name")
            and item.get("agent_run_id") != agent_run_id
            and status_agent_active(settings, item)
        }
        lease_path = lease_root / f"{agent_name}.json"
        if lease_path.is_file():
            try:
                lease = json.loads(lease_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                lease = {}
            leased_agent_run_id = lease.get("agent_run_id")
            if leased_agent_run_id and leased_agent_run_id != agent_run_id:
                try:
                    leased_status = read_status(settings, str(leased_agent_run_id))
                except WorkflowError:
                    leased_status = None
                if leased_status is not None:
                    if status_agent_active(settings, leased_status):
                        active_names.add(agent_name)
                elif lease.get("pid") == os.getpid():
                    active_names.add(agent_name)
        if agent_name in active_names:
            raise WorkflowError(f"agent name is already active: {agent_name}")
        atomic_write_json(
            lease_path,
            {
                "schema": "agent-workflow/agent-name-lease/v1",
                "agent_name": agent_name,
                "agent_run_id": agent_run_id,
                "interactive": interactive,
                "pid": os.getpid(),
                "claimed_at": utc_now(),
            },
        )
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
