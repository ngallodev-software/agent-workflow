from __future__ import annotations
import os, tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from .errors import WorkflowError
from .util import expand_path
def _xdg(name: str, fallback: str) -> Path:
    return expand_path(os.environ.get(name, fallback))
@dataclass(frozen=True)
class Settings:
    config_path: Path
    source_root: Path
    worktree_root: Path
    prompt_pack_root: Path
    state_root: Path
    terminal_backend: str = "tmux"
    stall_minutes: int = 10
    capture_lines: int = 50
    branch_prefix: str = "impl/"
    require_clean_source: bool = True
    preserve_failed_worktrees: bool = True
    archive_level: int = 19
    write_sha256: bool = True
    validate_before_archive: bool = True
    executors: dict[str, list[str]] = field(default_factory=dict)
def default_config_path() -> Path:
    return _xdg("XDG_CONFIG_HOME", "~/.config") / "agent-workflow" / "config.toml"
def defaults(path: Path | None = None) -> Settings:
    return Settings(
        config_path=path or default_config_path(),
        source_root=Path.home()/"src",
        worktree_root=_xdg("XDG_DATA_HOME", "~/.local/share")/"agent-workflow"/"worktrees",
        prompt_pack_root=Path.home()/"prompt-packs",
        state_root=_xdg("XDG_STATE_HOME", "~/.local/state")/"agent-workflow",
        executors={"codex":["codex","exec","--full-auto","-"],"claude":["claude","--print"]},
    )
def _nested(data: dict[str, Any], section: str, key: str, default: Any) -> Any:
    table = data.get(section, {})
    if not isinstance(table, dict):
        raise WorkflowError(f"config section [{section}] must be a table")
    return table.get(key, default)
def load_settings(path: Path | None = None) -> Settings:
    path = expand_path(path or default_config_path()); base = defaults(path)
    if not path.exists(): return base
    try: data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise WorkflowError(f"cannot read config {path}: {exc}") from exc
    executors = dict(base.executors)
    raw = data.get("executors", {})
    if not isinstance(raw, dict): raise WorkflowError("[executors] must contain executor tables")
    for name, entry in raw.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("command"), list):
            raise WorkflowError(f"executor {name!r} requires command = [..]")
        command = entry["command"]
        if not command or not all(isinstance(x,str) and x for x in command):
            raise WorkflowError(f"executor {name!r} command must be a non-empty string list")
        executors[name] = command
    stall=int(_nested(data,"terminal","stall_minutes",base.stall_minutes)); capture=int(_nested(data,"terminal","capture_lines",base.capture_lines)); level=int(_nested(data,"pack","archive_level",base.archive_level))
    if stall<1 or capture<1 or not 1<=level<=22: raise WorkflowError("invalid stall_minutes, capture_lines, or archive_level")
    return Settings(
        config_path=path,
        source_root=expand_path(_nested(data,"paths","source_root",base.source_root)),
        worktree_root=expand_path(_nested(data,"paths","worktree_root",base.worktree_root)),
        prompt_pack_root=expand_path(_nested(data,"paths","prompt_pack_root",base.prompt_pack_root)),
        state_root=expand_path(_nested(data,"paths","state_root",base.state_root)),
        terminal_backend=str(_nested(data,"terminal","backend",base.terminal_backend)),
        stall_minutes=stall,capture_lines=capture,
        branch_prefix=str(_nested(data,"git","branch_prefix",base.branch_prefix)),
        require_clean_source=bool(_nested(data,"git","require_clean_source",base.require_clean_source)),
        preserve_failed_worktrees=bool(_nested(data,"git","preserve_failed_worktrees",base.preserve_failed_worktrees)),
        archive_level=level,
        write_sha256=bool(_nested(data,"pack","write_sha256",base.write_sha256)),
        validate_before_archive=bool(_nested(data,"pack","validate_before_archive",base.validate_before_archive)),
        executors=executors,
    )
def as_dict(s: Settings) -> dict[str, Any]:
    return {"config_path":str(s.config_path),"paths":{"source_root":str(s.source_root),"worktree_root":str(s.worktree_root),"prompt_pack_root":str(s.prompt_pack_root),"state_root":str(s.state_root)},"terminal":{"backend":s.terminal_backend,"stall_minutes":s.stall_minutes,"capture_lines":s.capture_lines},"git":{"branch_prefix":s.branch_prefix,"require_clean_source":s.require_clean_source,"preserve_failed_worktrees":s.preserve_failed_worktrees},"pack":{"archive_level":s.archive_level,"write_sha256":s.write_sha256,"validate_before_archive":s.validate_before_archive},"executors":s.executors}
