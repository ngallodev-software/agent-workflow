"""Bounded, argv-only subprocess execution.

This is the only repository-owned module allowed to construct a subprocess.
The public helpers retain the small ``CompletedProcess``-like surface used by
Git and capability probes, while ``spawn`` is used by the runner for bounded
streaming execution.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .errors import WorkflowError


DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_GRACE_SECONDS = 2.0
DEFAULT_MAX_CAPTURE_BYTES = 1024 * 1024
DEFAULT_MAX_SPOOL_BYTES = 16 * 1024 * 1024
MAX_EXECUTABLE_DIGEST_BYTES = 512 * 1024 * 1024
_SECRET_OPTION = re.compile(
    r"(?:token|password|passwd|secret|api[-_]?key|auth(?:entication)?|credential|private[-_]?key)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class EnvironmentPolicy:
    """Explicit child environment policy.

    Values in ``values`` are caller-supplied named values. Ambient values are
    copied only when their names appear in ``allowlist``. ``unsafe_inherit``
    is intentionally explicit and is recorded in the result; governed launch
    paths do not use it.
    """

    allowlist: tuple[str, ...] = (
        "TMUX",
        "TMUX_PANE",
        "FAKE_TMUX_STATE",
        "FAKE_AGENT_MODE",
        "FAKE_AGENT_DELAY",
        "FAKE_AGENT_RESULT_JSON",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    )
    values: Mapping[str, str] = field(default_factory=dict)
    unsafe_inherit: bool = False


@dataclass(frozen=True)
class ProcessRequest:
    argv: tuple[str, ...] | Sequence[str]
    cwd: Path | None = None
    timeout_seconds: float | None = DEFAULT_TIMEOUT_SECONDS
    grace_seconds: float = DEFAULT_GRACE_SECONDS
    create_process_group: bool = True
    max_stdout_bytes: int = DEFAULT_MAX_CAPTURE_BYTES
    max_stderr_bytes: int = DEFAULT_MAX_CAPTURE_BYTES
    stdout_spool: Path | None = None
    stderr_spool: Path | None = None
    max_spool_bytes: int = DEFAULT_MAX_SPOOL_BYTES
    environment: EnvironmentPolicy = field(default_factory=EnvironmentPolicy)
    secret_values: tuple[str, ...] = ()
    secret_argv_positions: tuple[int, ...] = ()
    probe_version: bool = False
    digest_executable: bool = False
    interactive: bool = False


@dataclass(frozen=True)
class ExecutableIdentity:
    requested: str
    resolved_path: str | None
    version: str | None = None
    sha256: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "requested": self.requested,
            "resolved_path": self.resolved_path,
            "version": self.version,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class ProcessResult:
    argv: tuple[str, ...]
    resolved_executable: str | None
    executable_version: str | None
    executable_sha256: str | None
    stdout: bytes | str
    stderr: bytes | str
    returncode: int
    exit_code: int | None
    signal: int | None
    timed_out: bool
    cancelled: bool
    stdout_truncated: bool
    stderr_truncated: bool
    stdout_bytes: int
    stderr_bytes: int
    stdout_spool: str | None
    stderr_spool: str | None
    duration_seconds: float
    error_category: str
    environment_policy: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error_category == "completed"

    def as_dict(self, *, include_output: bool = True) -> dict[str, object]:
        result: dict[str, object] = {
            "argv": list(self.argv),
            "resolved_executable": self.resolved_executable,
            "executable_version": self.executable_version,
            "executable_sha256": self.executable_sha256,
            "returncode": self.returncode,
            "exit_code": self.exit_code,
            "signal": self.signal,
            "timed_out": self.timed_out,
            "cancelled": self.cancelled,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "stdout_spool": self.stdout_spool,
            "stderr_spool": self.stderr_spool,
            "duration_seconds": self.duration_seconds,
            "error_category": self.error_category,
            "environment_policy": self.environment_policy,
        }
        if include_output:
            result["stdout"] = self.stdout
            result["stderr"] = self.stderr
        return result


def _secret_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()[:16]


def _redaction(value: str) -> str:
    return f"<redacted:{_secret_digest(value)}>"


def redact_text(value: str, secret_values: Iterable[str] = ()) -> str:
    redacted = value
    for secret in sorted({item for item in secret_values if item}, key=len, reverse=True):
        redacted = redacted.replace(secret, _redaction(secret))
    return redacted


def redact_bytes(value: bytes, secret_values: Iterable[str] = ()) -> bytes:
    redacted = value
    for secret in sorted({item for item in secret_values if item}, key=len, reverse=True):
        needle = secret.encode("utf-8", errors="surrogatepass")
        redacted = redacted.replace(needle, _redaction(secret).encode())
    return redacted


def secret_values_from_argv(argv: Sequence[str]) -> tuple[str, ...]:
    """Return values following secret-looking options for launch diagnostics."""
    values: list[str] = []
    for index, item in enumerate(argv):
        option, separator, value = item.partition("=")
        if separator and _SECRET_OPTION.search(option):
            values.append(value)
        elif _SECRET_OPTION.search(item) and index + 1 < len(argv):
            values.append(argv[index + 1])
    return tuple(value for value in values if value)


def redact_argv(
    argv: Sequence[str],
    *,
    secret_values: Iterable[str] = (),
    secret_positions: Iterable[int] = (),
) -> tuple[str, ...]:
    secrets = tuple(secret_values)
    positions = set(secret_positions)
    result: list[str] = []
    for index, item in enumerate(argv):
        if index in positions:
            result.append(_redaction(item))
            continue
        option, separator, value = item.partition("=")
        if separator and _SECRET_OPTION.search(option):
            result.append(option + "=" + _redaction(value))
            continue
        if _SECRET_OPTION.search(item) and index + 1 < len(argv):
            result.append(item)
            positions.add(index + 1)
            continue
        result.append(redact_text(item, secrets))
    return tuple(result)


def _validate_limit(name: str, value: int) -> None:
    if isinstance(value, bool) or value < 0:
        raise WorkflowError(f"{name} must be a non-negative integer")


def _command(request: ProcessRequest) -> tuple[str, ...]:
    if isinstance(request.argv, (str, bytes)):
        raise WorkflowError("process argv must be a non-empty sequence, not a command string")
    command = tuple(str(item) for item in request.argv)
    if not command or any("\x00" in item for item in command):
        raise WorkflowError("process argv must contain non-empty NUL-free arguments")
    if not command[0]:
        raise WorkflowError("process executable must not be empty")
    _validate_limit("max_stdout_bytes", request.max_stdout_bytes)
    _validate_limit("max_stderr_bytes", request.max_stderr_bytes)
    _validate_limit("max_spool_bytes", request.max_spool_bytes)
    if request.timeout_seconds is not None and request.timeout_seconds <= 0:
        raise WorkflowError("timeout_seconds must be positive or None")
    if request.grace_seconds < 0:
        raise WorkflowError("grace_seconds must be non-negative")
    return command


def _controlled_path(executable: str, resolved: str | None) -> str:
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
        "PATH": _controlled_path(command[0], resolved),
        "LC_ALL": "C",
        "LANG": "C",
        "LANGUAGE": "C",
        "TZ": "UTC",
    }
    if policy.unsafe_inherit:
        environment.update({str(key): str(value) for key, value in os.environ.items()})
        environment["PATH"] = _controlled_path(command[0], resolved)
    else:
        for name in policy.allowlist:
            if name in os.environ:
                environment[name] = os.environ[name]
    for name, value in policy.values.items():
        if not isinstance(name, str) or not name or "=" in name or "\x00" in name:
            raise WorkflowError(f"invalid environment variable name: {name!r}")
        environment[name] = str(value)
    return environment, ("unsafe-inherit" if policy.unsafe_inherit else "controlled"), (
        tuple(str(value) for value in policy.values.values())
    )


def _digest_file(path: Path) -> str | None:
    try:
        info = path.stat()
    except OSError:
        return None
    if not path.is_file() or info.st_size > MAX_EXECUTABLE_DIGEST_BYTES:
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def resolve_executable(
    command: Sequence[str], *, digest: bool = False
) -> ExecutableIdentity:
    requested = command[0]
    resolved = shutil.which(requested, path=os.environ.get("PATH", DEFAULT_PATH))
    if resolved is None and os.sep in requested:
        candidate = Path(requested)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            resolved = str(candidate)
    return ExecutableIdentity(
        requested=requested,
        resolved_path=str(Path(resolved).resolve()) if resolved else None,
        sha256=_digest_file(Path(resolved)) if digest and resolved else None,
    )


def _probe_version(path: str, secret_values: Iterable[str]) -> str | None:
    result = _run_request(
        ProcessRequest(
            argv=(path, "--version"),
            timeout_seconds=10,
            max_stdout_bytes=16 * 1024,
            max_stderr_bytes=16 * 1024,
            secret_values=tuple(secret_values),
        ),
        text=True,
        check=False,
        probe_identity=False,
    )
    if result.returncode != 0:
        return None
    value = str(result.stdout or result.stderr).strip()
    return value or None


def executable_identity(
    command: Sequence[str], *, probe_version: bool = False, digest: bool = False
) -> ExecutableIdentity:
    identity = resolve_executable(command, digest=digest)
    if probe_version and identity.resolved_path:
        return ExecutableIdentity(
            requested=identity.requested,
            resolved_path=identity.resolved_path,
            version=_probe_version(identity.resolved_path, ()),
            sha256=identity.sha256,
        )
    return identity


class _BoundedReader:
    def __init__(
        self,
        stream: object,
        limit: int,
        spool: Path | None,
        max_spool_bytes: int,
        secret_values: tuple[str, ...],
    ) -> None:
        self._stream = stream
        self._limit = limit
        self._spool_path = spool
        self._max_spool_bytes = max_spool_bytes
        self._secret_values = secret_values
        self._retained = bytearray()
        self._spooled = 0
        self._raw_seen = 0
        self._truncated = False
        self._drained = False
        self._spool_stream = None
        if spool is not None:
            if spool.exists() and spool.is_symlink():
                raise WorkflowError(f"output spool must not be a symlink: {spool}")
            spool.parent.mkdir(parents=True, exist_ok=True)
            self._spool_stream = spool.open("wb")

    @property
    def retained(self) -> bytes:
        return bytes(self._retained)

    @property
    def truncated(self) -> bool:
        return self._truncated

    @property
    def bytes_seen(self) -> int:
        return self._raw_seen

    def _retain(self, raw: bytes) -> bytes:
        self._raw_seen += len(raw)
        safe = redact_bytes(raw, self._secret_values)
        remaining = max(0, self._limit - len(self._retained))
        visible = safe[:remaining]
        if len(visible) < len(safe) or len(self._retained) + len(safe) > self._limit:
            self._truncated = True
        self._retained.extend(visible)
        if self._spool_stream is not None and self._spooled < self._max_spool_bytes:
            spool_remaining = self._max_spool_bytes - self._spooled
            stored = visible[:spool_remaining]
            self._spool_stream.write(stored)
            self._spool_stream.flush()
            self._spooled += len(stored)
        return visible

    def _read_raw(self, size: int = 65536) -> bytes:
        if self._drained:
            return b""
        data = self._stream.read(size)
        if not data:
            self._drained = True
            return b""
        return data

    def read(self, size: int = 65536) -> bytes:
        if self._limit == len(self._retained) and not self._drained:
            while True:
                discarded = self._read_raw()
                if not discarded:
                    break
                self._raw_seen += len(discarded)
                self._truncated = True
            return b""
        data = self._read_raw(max(1, min(size, 65536)))
        return self._retain(data) if data else b""

    def readline(self) -> bytes:
        # Keep each read bounded even when a child emits a binary/no-newline
        # stream. A caller using readline therefore cannot allocate an
        # unbounded line.
        pieces = bytearray()
        while len(pieces) < 65536:
            chunk = self.read(min(65536 - len(pieces), 65536))
            if not chunk:
                break
            pieces.extend(chunk)
            if b"\n" in chunk:
                break
        return bytes(pieces)

    def close(self) -> None:
        try:
            self._stream.close()
        finally:
            if self._spool_stream is not None:
                self._spool_stream.close()


class ManagedProcess:
    def __init__(self, request: ProcessRequest, command: tuple[str, ...]) -> None:
        self.request = request
        self.command = command
        self.identity = resolve_executable(command, digest=request.digest_executable)
        self.redacted_argv = redact_argv(
            command,
            secret_values=request.secret_values,
            secret_positions=request.secret_argv_positions,
        )
        environment, policy_name, env_secrets = build_environment(command, request.environment)
        self.environment_policy = policy_name
        self.secret_values = tuple(dict.fromkeys((*request.secret_values, *env_secrets)))
        try:
            self.process = subprocess.Popen(
                list(command),
                cwd=request.cwd,
                env=environment,
                stdin=subprocess.PIPE if not request.interactive else None,
                stdout=subprocess.PIPE if not request.interactive else None,
                stderr=subprocess.PIPE if not request.interactive else None,
                shell=False,
                start_new_session=request.create_process_group and not request.interactive,
            )
        except OSError as exc:
            raise _process_error(self.redacted_argv, exc) from exc
        self.stdout = (
            _BoundedReader(
                self.process.stdout,
                request.max_stdout_bytes,
                request.stdout_spool,
                request.max_spool_bytes,
                self.secret_values,
            )
            if self.process.stdout is not None
            else None
        )
        self.stderr = (
            _BoundedReader(
                self.process.stderr,
                request.max_stderr_bytes,
                request.stderr_spool,
                request.max_spool_bytes,
                self.secret_values,
            )
            if self.process.stderr is not None
            else None
        )
        self.started = time.monotonic()
        self.cancelled = False
        self.timed_out = False
        self._closed = False

    @property
    def pid(self) -> int:
        return self.process.pid

    def poll(self) -> int | None:
        return self.process.poll()

    def send_signal(self, signum: int) -> None:
        if self.process.poll() is not None:
            return
        if self.request.create_process_group and not self.request.interactive:
            try:
                os.killpg(self.process.pid, signum)
            except ProcessLookupError:
                pass
        else:
            self.process.send_signal(signum)

    def wait(self, timeout: float | None = None) -> int:
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.cancel(timed_out=True)
            return self.process.wait()

    def wait_for(self, timeout: float) -> int | None:
        """Wait without changing process state when the interval expires."""
        try:
            return self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def cancel(self, *, timed_out: bool = False) -> int:
        self.cancelled = not timed_out
        self.timed_out = timed_out
        self.send_signal(signal.SIGTERM)
        try:
            return self.process.wait(timeout=self.request.grace_seconds)
        except subprocess.TimeoutExpired:
            self.send_signal(signal.SIGKILL)
            return self.process.wait()

    def close_streams(self) -> None:
        if self._closed:
            return
        self._closed = True
        for stream in (self.stdout, self.stderr):
            if stream is not None:
                stream.close()

    def result(self, returncode: int | None = None) -> ProcessResult:
        code = self.process.returncode if returncode is None else returncode
        if code is None:
            code = self.process.wait()
        timed_out = self.timed_out
        cancelled = self.cancelled
        if code < 0:
            exit_code = None
            signal_number = -code
        else:
            exit_code = code
            signal_number = None
        if timed_out:
            category = "timeout"
        elif cancelled:
            category = "cancelled"
        elif code < 0:
            category = "signal"
        elif code == 0:
            category = "completed"
        else:
            category = "nonzero-exit"
        stdout = self.stdout.retained if self.stdout is not None else b""
        stderr = self.stderr.retained if self.stderr is not None else b""
        return ProcessResult(
            argv=self.redacted_argv,
            resolved_executable=self.identity.resolved_path,
            executable_version=None,
            executable_sha256=self.identity.sha256,
            stdout=stdout,
            stderr=stderr,
            returncode=code,
            exit_code=exit_code,
            signal=signal_number,
            timed_out=timed_out,
            cancelled=cancelled,
            stdout_truncated=self.stdout.truncated if self.stdout is not None else False,
            stderr_truncated=self.stderr.truncated if self.stderr is not None else False,
            stdout_bytes=self.stdout.bytes_seen if self.stdout is not None else 0,
            stderr_bytes=self.stderr.bytes_seen if self.stderr is not None else 0,
            stdout_spool=str(self.request.stdout_spool) if self.request.stdout_spool else None,
            stderr_spool=str(self.request.stderr_spool) if self.request.stderr_spool else None,
            duration_seconds=round(time.monotonic() - self.started, 6),
            error_category=category,
            environment_policy=self.environment_policy,
        )


def spawn(request: ProcessRequest) -> ManagedProcess:
    command = _command(request)
    return ManagedProcess(request, command)


def _process_error(argv: Sequence[str], exc: OSError) -> WorkflowError:
    if isinstance(exc, FileNotFoundError):
        category = "not-found"
    elif isinstance(exc, PermissionError):
        category = "permission"
    else:
        category = "spawn-error"
    return WorkflowError(f"{category}: {' '.join(argv)}")


def _run_request(
    request: ProcessRequest,
    *,
    text: bool,
    check: bool,
    probe_identity: bool = True,
) -> ProcessResult:
    command = _command(request)
    try:
        process = spawn(request)
    except WorkflowError as exc:
        if check:
            raise
        category = "not-found" if str(exc).startswith("not-found:") else "spawn-error"
        output: bytes | str = "" if text else b""
        return ProcessResult(
            argv=redact_argv(
                command,
                secret_values=request.secret_values,
                secret_positions=request.secret_argv_positions,
            ),
            resolved_executable=None,
            executable_version=None,
            executable_sha256=None,
            stdout=output,
            stderr=output,
            returncode=127,
            exit_code=127,
            signal=None,
            timed_out=False,
            cancelled=False,
            stdout_truncated=False,
            stderr_truncated=False,
            stdout_bytes=0,
            stderr_bytes=0,
            stdout_spool=None,
            stderr_spool=None,
            duration_seconds=0.0,
            error_category=category,
            environment_policy="controlled",
        )
    if process.process.stdin is not None:
        process.process.stdin.close()
    stdout_data: list[bytes] = []
    stderr_data: list[bytes] = []

    def drain(reader: _BoundedReader | None, target: list[bytes]) -> None:
        if reader is None:
            return
        try:
            for chunk in iter(reader.read, b""):
                target.append(chunk)
        finally:
            reader.close()

    threads = [
        threading.Thread(target=drain, args=(process.stdout, stdout_data), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr_data), daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        if request.timeout_seconds is None:
            code = process.wait()
        else:
            try:
                code = process.process.wait(timeout=request.timeout_seconds)
            except subprocess.TimeoutExpired:
                code = process.cancel(timed_out=True)
    except KeyboardInterrupt:
        code = process.cancel()
        raise
    finally:
        for thread in threads:
            thread.join(timeout=max(1.0, request.grace_seconds + 1.0))
        process.close_streams()
    result = process.result(code)
    output_type = str if text else bytes
    if text:
        result = ProcessResult(
            **{
                **result.__dict__,
                "stdout": result.stdout.decode("utf-8", errors="replace"),
                "stderr": result.stderr.decode("utf-8", errors="replace"),
            }
        )
    if probe_identity and request.probe_version and result.resolved_executable:
        version = _probe_version(result.resolved_executable, request.secret_values)
        result = ProcessResult(**{**result.__dict__, "executable_version": version})
    if check and result.returncode:
        detail = redact_text(
            str(result.stderr or result.stdout).strip(),
            request.secret_values,
        )
        suffix = f"\n{detail}" if detail else ""
        raise WorkflowError(
            f"command {result.error_category} ({result.returncode}): "
            f"{' '.join(result.argv)}{suffix}"
        )
    return result


def run(
    args: Iterable[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout_seconds: float | None = DEFAULT_TIMEOUT_SECONDS,
    max_stdout_bytes: int = DEFAULT_MAX_CAPTURE_BYTES,
    max_stderr_bytes: int = DEFAULT_MAX_CAPTURE_BYTES,
    environment: EnvironmentPolicy | None = None,
    secret_values: Iterable[str] = (),
    secret_argv_positions: Iterable[int] = (),
    probe_version: bool = False,
    digest_executable: bool = False,
) -> ProcessResult:
    return _run_request(
        ProcessRequest(
            argv=tuple(str(item) for item in args),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            max_stdout_bytes=max_stdout_bytes,
            max_stderr_bytes=max_stderr_bytes,
            environment=environment or EnvironmentPolicy(),
            secret_values=tuple(secret_values),
            secret_argv_positions=tuple(secret_argv_positions),
            probe_version=probe_version,
            digest_executable=digest_executable,
        ),
        text=True,
        check=check,
    )


def run_bytes(
    args: Iterable[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout_seconds: float | None = DEFAULT_TIMEOUT_SECONDS,
    max_stdout_bytes: int = DEFAULT_MAX_CAPTURE_BYTES,
    max_stderr_bytes: int = DEFAULT_MAX_CAPTURE_BYTES,
    environment: EnvironmentPolicy | None = None,
    secret_values: Iterable[str] = (),
    secret_argv_positions: Iterable[int] = (),
    probe_version: bool = False,
    digest_executable: bool = False,
) -> ProcessResult:
    return _run_request(
        ProcessRequest(
            argv=tuple(str(item) for item in args),
            cwd=cwd,
            timeout_seconds=timeout_seconds,
            max_stdout_bytes=max_stdout_bytes,
            max_stderr_bytes=max_stderr_bytes,
            environment=environment or EnvironmentPolicy(),
            secret_values=tuple(secret_values),
            secret_argv_positions=tuple(secret_argv_positions),
            probe_version=probe_version,
            digest_executable=digest_executable,
        ),
        text=False,
        check=check,
    )


def require_command(name: str) -> str:
    path = shutil.which(name, path=os.environ.get("PATH", DEFAULT_PATH))
    if not path:
        raise WorkflowError(f"required command not found on PATH: {name}")
    return path


def executor_identity(command: Sequence[str]) -> ExecutableIdentity:
    return executable_identity(command, probe_version=True, digest=True)
