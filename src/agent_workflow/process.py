"""Bounded, argv-only subprocess execution.

This is the only repository-owned module allowed to construct a subprocess.
The public helpers retain the small ``CompletedProcess``-like surface used by
Git and capability probes, while ``spawn`` is used by the runner for bounded
streaming execution.
"""

from __future__ import annotations

import hashlib
import os
import selectors
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from .errors import WorkflowError
from .runtime.environment import DEFAULT_PATH, EnvironmentPolicy, build_environment
from .runtime.redaction import (
    redact_argv,
    redact_bytes,
    redact_text,
    secret_values_from_argv,
)


DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_GRACE_SECONDS = 2.0
DEFAULT_MAX_CAPTURE_BYTES = 1024 * 1024
DEFAULT_MAX_SPOOL_BYTES = 16 * 1024 * 1024
MAX_EXECUTABLE_DIGEST_BYTES = 512 * 1024 * 1024

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
    stdin_data: bytes | None = None


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
        try:
            data = os.read(self._stream.fileno(), size)
        except (OSError, ValueError):
            self._drained = True
            return b""
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

    def force_close_stream(self) -> None:
        """Close the pipe descriptor without waiting on another thread's buffered read lock."""
        try:
            descriptor = self._stream.fileno()
        except (AttributeError, OSError, ValueError):
            return
        try:
            os.close(descriptor)
        except OSError:
            pass

    def close(self) -> None:
        try:
            try:
                self._stream.close()
            except OSError:
                pass
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
                bufsize=0,
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

    def close_after_completion(self) -> int:
        """Stop an executor after a host-validated terminal completion.

        This is deliberately distinct from operator cancellation: the raw
        process result still records the signal, while the runner records the
        completion-terminated reason that authorized it.
        """
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



@dataclass(frozen=True)
class DetachedProcess:
    """Identity for a headless process started without captured stdio."""

    pid: int
    process_group_id: int
    argv: tuple[str, ...]
    resolved_executable: str | None
    environment_policy: str


def spawn_detached(request: ProcessRequest) -> DetachedProcess:
    """Start an AW-owned headless worker and return without waiting.

    Detached workers deliberately inherit no terminal and own a new process
    group so lifecycle controls can address execution semantically rather than
    through a terminal host.
    """
    if request.interactive:
        raise WorkflowError("detached workers cannot be interactive")
    if not request.create_process_group:
        raise WorkflowError("detached workers require an isolated process group")
    if request.stdin_data is not None:
        raise WorkflowError("detached workers do not accept stdin_data")
    command = _command(request)
    identity = resolve_executable(command, digest=request.digest_executable)
    redacted = redact_argv(
        command,
        secret_values=request.secret_values,
        secret_positions=request.secret_argv_positions,
    )
    environment, policy_name, _env_secrets = build_environment(command, request.environment)
    try:
        child = subprocess.Popen(
            list(command),
            cwd=request.cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:
        raise _process_error(redacted, exc) from exc
    return DetachedProcess(
        pid=child.pid,
        process_group_id=child.pid,
        argv=redacted,
        resolved_executable=identity.resolved_path,
        environment_policy=policy_name,
    )

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

    # Drain all pipes from the owning thread. Closing a pipe descriptor from a
    # separate reader thread is unsafe: the operating system can immediately
    # reuse that descriptor for a later child, leaving the old reader attached
    # to the new process. A selector keeps reads, writes, timeout handling, and
    # descriptor closure in one deterministic lifecycle.
    selector = selectors.DefaultSelector()
    stdin_view = memoryview(request.stdin_data or b"")
    stdin_offset = 0
    read_streams: dict[int, _BoundedReader] = {}
    exit_observed_at: float | None = None
    descendants_terminated = False
    descendants_killed = False

    def register_reader(reader: _BoundedReader | None) -> None:
        if reader is None:
            return
        descriptor = reader._stream.fileno()
        os.set_blocking(descriptor, False)
        read_streams[descriptor] = reader
        selector.register(descriptor, selectors.EVENT_READ, ("read", reader))

    def close_stdin() -> None:
        stream = process.process.stdin
        if stream is None:
            return
        descriptor = stream.fileno()
        try:
            selector.unregister(descriptor)
        except (KeyError, ValueError):
            pass
        try:
            stream.close()
        except OSError:
            pass

    def signal_group(signum: int) -> None:
        if not request.create_process_group or request.interactive:
            return
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

    try:
        if not request.interactive:
            register_reader(process.stdout)
            register_reader(process.stderr)
            if process.process.stdin is not None:
                descriptor = process.process.stdin.fileno()
                if stdin_view:
                    os.set_blocking(descriptor, False)
                    selector.register(descriptor, selectors.EVENT_WRITE, ("write", None))
                else:
                    close_stdin()

        deadline = (
            None
            if request.timeout_seconds is None
            else process.started + request.timeout_seconds
        )
        while True:
            now = time.monotonic()
            code = process.poll()
            if code is not None and exit_observed_at is None:
                exit_observed_at = now

            if code is None and deadline is not None and now >= deadline:
                process.timed_out = True
                signal_group(signal.SIGTERM)
                try:
                    process.process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    process.process.wait(timeout=request.grace_seconds)
                except subprocess.TimeoutExpired:
                    signal_group(signal.SIGKILL)
                    try:
                        process.process.kill()
                    except ProcessLookupError:
                        pass
                    process.process.wait()
                code = process.process.returncode
                exit_observed_at = time.monotonic()

            # A direct child can exit while descendants retain its output
            # descriptors. Terminate only that child's isolated process group,
            # then drain the resulting EOF. This avoids both indefinite waits
            # and cross-process descriptor reuse.
            if exit_observed_at is not None and read_streams:
                elapsed = now - exit_observed_at
                if elapsed >= 0.2 and not descendants_terminated:
                    signal_group(signal.SIGTERM)
                    descendants_terminated = True
                if elapsed >= max(0.2, request.grace_seconds) and not descendants_killed:
                    signal_group(signal.SIGKILL)
                    descendants_killed = True
                if elapsed >= max(1.0, request.grace_seconds + 0.5):
                    for descriptor, reader in list(read_streams.items()):
                        try:
                            selector.unregister(descriptor)
                        except (KeyError, ValueError):
                            pass
                        reader._drained = True
                        read_streams.pop(descriptor, None)

            stdin_registered = False
            if process.process.stdin is not None:
                try:
                    selector.get_key(process.process.stdin.fileno())
                    stdin_registered = True
                except (KeyError, ValueError, OSError):
                    pass
            if code is not None and not read_streams and not stdin_registered:
                break

            timeout = 0.1
            if deadline is not None and code is None:
                timeout = max(0.0, min(timeout, deadline - now))
            events = selector.select(timeout)
            for key, _mask in events:
                kind, reader = key.data
                descriptor = key.fd
                if kind == "write":
                    try:
                        written = os.write(descriptor, stdin_view[stdin_offset:])
                        stdin_offset += written
                    except (BrokenPipeError, OSError):
                        stdin_offset = len(stdin_view)
                    if stdin_offset >= len(stdin_view):
                        close_stdin()
                    continue

                assert reader is not None
                try:
                    raw = os.read(descriptor, 65536)
                except BlockingIOError:
                    continue
                except OSError:
                    raw = b""
                if raw:
                    reader._retain(raw)
                else:
                    reader._drained = True
                    try:
                        selector.unregister(descriptor)
                    except (KeyError, ValueError):
                        pass
                    read_streams.pop(descriptor, None)

        code = process.process.returncode
        if code is None:
            code = process.process.wait()
    except KeyboardInterrupt:
        process.cancelled = True
        signal_group(signal.SIGTERM)
        try:
            process.process.terminate()
        except ProcessLookupError:
            pass
        try:
            process.process.wait(timeout=request.grace_seconds)
        except subprocess.TimeoutExpired:
            signal_group(signal.SIGKILL)
            try:
                process.process.kill()
            except ProcessLookupError:
                pass
            process.process.wait()
        raise
    finally:
        try:
            selector.close()
        finally:
            if process.process.stdin is not None and not process.process.stdin.closed:
                try:
                    process.process.stdin.close()
                except OSError:
                    pass
            process.close_streams()

    result = process.result(code)
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
    input_text: str | None = None,
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
            stdin_data=input_text.encode("utf-8") if input_text is not None else None,
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
    input_bytes: bytes | None = None,
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
            stdin_data=input_bytes,
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
