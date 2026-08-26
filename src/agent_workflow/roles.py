from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable

import yaml

from .contracts import validate_instance
from .errors import WorkflowError
from .path import absolute_path, read_regular_file

ROLE_SCHEMA = "agent-workflow/agent-role/v1"
_ROLE_SUFFIXES = {".yaml", ".yml", ".json"}
_FORBIDDEN_PUBLIC_KEYS = {
    "provider",
    "executor",
    "model",
    "model_alias",
    "runtime",
    "runtime_alias",
    "credential",
    "credentials",
    "authentication",
    "billing",
}


@dataclass(frozen=True)
class AgentRole:
    value: dict[str, Any]
    digest: str
    instructions_markdown: str | None = None

    @property
    def role_id(self) -> str:
        return str(self.value["id"])

    @property
    def command_profile(self) -> str:
        """Return the small command profile implied by this public role contract."""
        capabilities = {str(item) for item in self.value.get("capabilities", [])}
        if "agent-workflow.review.publish" in capabilities:
            return "review"
        return "implementation"

    def public_dict(self) -> dict[str, Any]:
        result = dict(self.value)
        # The source filename is not part of the public contract. Replace the
        # instruction reference with its content so callers never need private
        # filesystem knowledge to understand the role.
        result.pop("instructions", None)
        if self.instructions_markdown is not None:
            result["instructions_markdown"] = self.instructions_markdown
        result["digest"] = self.digest
        return result


def _canonical_bytes(value: dict[str, Any], instructions_markdown: str | None) -> bytes:
    normalized: dict[str, Any] = {"role": value}
    if instructions_markdown is not None:
        normalized["instructions_markdown"] = instructions_markdown
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _reject_identity_leaks(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_PUBLIC_KEYS:
                raise WorkflowError(
                    f"agent role contains private runtime/provider field at {path}.{key}"
                )
            _reject_identity_leaks(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_identity_leaks(child, path=f"{path}[{index}]")


def _decode_structured(data: bytes, *, label: str, suffix: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkflowError(f"agent role is not UTF-8: {label}") from exc
    try:
        value = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise WorkflowError(f"invalid agent role document: {label}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"agent role must be an object: {label}")
    return value


def _load_role_bytes(
    data: bytes,
    *,
    label: str,
    suffix: str,
    markdown_reader,
) -> AgentRole:
    value = _decode_structured(data, label=label, suffix=suffix)
    if value.get("schema") != ROLE_SCHEMA:
        raise WorkflowError(f"unsupported agent role schema in {label}")
    _reject_identity_leaks(value)
    validate_instance(value, ROLE_SCHEMA, artifact=label)

    instructions_markdown: str | None = None
    instruction_ref = value.get("instructions")
    if instruction_ref is not None:
        if not isinstance(instruction_ref, str) or not instruction_ref:
            raise WorkflowError(f"agent role instructions must be a relative Markdown path: {label}")
        relative = Path(instruction_ref)
        if (
            relative.is_absolute()
            or relative.suffix.lower() != ".md"
            or ".." in relative.parts
            or relative.as_posix() != instruction_ref
        ):
            raise WorkflowError(f"unsafe agent role instruction path in {label}: {instruction_ref}")
        try:
            instructions_markdown = markdown_reader(instruction_ref)
        except (OSError, WorkflowError) as exc:
            raise WorkflowError(
                f"cannot read agent role instructions {instruction_ref!r} for {label}"
            ) from exc
        if not instructions_markdown.strip():
            raise WorkflowError(f"agent role instructions are empty for {label}")

    digest = hashlib.sha256(_canonical_bytes(value, instructions_markdown)).hexdigest()
    return AgentRole(value=value, digest=digest, instructions_markdown=instructions_markdown)


def _builtin_roles() -> Iterable[AgentRole]:
    root = files("agent_workflow").joinpath("assets", "roles")
    for item in sorted(root.iterdir(), key=lambda entry: entry.name):
        suffix = Path(item.name).suffix.lower()
        if suffix not in _ROLE_SUFFIXES:
            continue

        def read_markdown(relative: str, *, _root=root) -> str:
            target = _root.joinpath(relative)
            return target.read_text(encoding="utf-8")

        yield _load_role_bytes(
            item.read_bytes(),
            label=f"builtin:{item.name}",
            suffix=suffix,
            markdown_reader=read_markdown,
        )


def _filesystem_roles(paths: tuple[Path, ...]) -> Iterable[AgentRole]:
    candidates: list[Path] = []
    for configured in paths:
        path = absolute_path(configured)
        if path.is_dir():
            candidates.extend(
                child for child in sorted(path.iterdir()) if child.suffix.lower() in _ROLE_SUFFIXES
            )
        elif path.suffix.lower() in _ROLE_SUFFIXES:
            candidates.append(path)
        else:
            raise WorkflowError(f"agent role path is neither a role file nor directory: {path}")

    for path in candidates:
        read = read_regular_file(path)
        root = path.parent

        def read_markdown(relative: str, *, _root=root) -> str:
            target = absolute_path(_root / relative)
            try:
                target.relative_to(absolute_path(_root))
            except ValueError as exc:
                raise WorkflowError(f"agent role instructions escape role directory: {relative}") from exc
            return read_regular_file(target).data.decode("utf-8")

        yield _load_role_bytes(
            read.data,
            label=str(path),
            suffix=path.suffix.lower(),
            markdown_reader=read_markdown,
        )


def load_roles(paths: tuple[Path, ...] = ()) -> dict[str, AgentRole]:
    result: dict[str, AgentRole] = {}
    for role in (*_builtin_roles(), *_filesystem_roles(paths)):
        if role.role_id in result:
            raise WorkflowError(f"duplicate agent role ID: {role.role_id}")
        result[role.role_id] = role
    return result


def public_role_catalog(paths: tuple[Path, ...] = ()) -> dict[str, Any]:
    roles = load_roles(paths)
    return {
        "schema": "agent-workflow/agent-role-catalog/v1",
        "roles": [roles[role_id].public_dict() for role_id in sorted(roles)],
    }
