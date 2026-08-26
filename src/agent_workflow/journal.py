"""Hardened append-only journal and lock primitives.

This module owns the filesystem mechanics shared by Agent-Workflow journals:
no-follow descriptor opens, single-link regular-file enforcement, advisory
locking, bounded stable reads, complete writes, and fsync durability. Domain
modules remain responsible for record schemas and cross-record semantics.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generic, Iterator, Mapping, TypeVar

from .errors import WorkflowError
from .path import require_directory

T = TypeVar("T")


class JournalCapacityError(WorkflowError):
    """Raised when a bounded journal cannot accept another record."""


DEFAULT_MAX_JOURNAL_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_RECORD_BYTES = 128 * 1024
_READ_CHUNK = 1024 * 1024


@dataclass(frozen=True)
class JournalTransactionResult(Generic[T]):
    """Result of a locked journal transaction.

    ``record`` is appended when non-None. ``value`` is returned to the caller,
    which allows idempotent transactions to return an existing record without
    writing another line.
    """

    value: T
    record: Mapping[str, Any] | None = None


def canonical_json_line(value: Mapping[str, Any]) -> bytes:
    """Encode one canonical UTF-8 JSONL record."""
    return (
        json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _open_parent(path: Path, *, create_parent: bool) -> tuple[int, Path]:
    parent = Path(path).parent
    if create_parent:
        parent.mkdir(parents=True, exist_ok=True)
    parent = require_directory(parent, label="journal parent")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        return os.open(parent, flags), parent
    except OSError as exc:
        raise WorkflowError(f"cannot open journal parent without following links: {parent}") from exc


def _validate_open_file(descriptor: int, path: Path, *, single_link: bool) -> os.stat_result:
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        raise WorkflowError(f"journal must be a regular file: {path}")
    if single_link and info.st_nlink != 1:
        raise WorkflowError(f"journal must not be hard linked: {path}")
    return info


@contextlib.contextmanager
def locked_descriptor(descriptor: int, *, exclusive: bool) -> Iterator[int]:
    """Hold an advisory lock on an already-open descriptor."""
    fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    try:
        yield descriptor
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


@contextlib.contextmanager
def locked_file(
    path: Path,
    *,
    exclusive: bool,
    create: bool = False,
    create_parent: bool = False,
    mode: int = 0o600,
    single_link: bool = True,
) -> Iterator[tuple[int, bool]]:
    """Open and lock a regular non-symlink file by descriptor.

    Returns ``(descriptor, created)``. Every path component is opened without
    following symlinks and, by default, hard-linked final files are rejected.
    The descriptor is unlocked and closed on exit. A newly-created directory
    entry is fsynced before return from the context manager.
    """
    path = Path(path)
    parent_fd, parent = _open_parent(path, create_parent=create_parent)
    descriptor: int | None = None
    created = False
    try:
        base_flags = os.O_RDWR if exclusive or create else os.O_RDONLY
        base_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        if create:
            try:
                descriptor = os.open(
                    path.name,
                    base_flags | os.O_CREAT | os.O_EXCL,
                    mode,
                    dir_fd=parent_fd,
                )
                created = True
            except FileExistsError:
                try:
                    descriptor = os.open(path.name, base_flags, dir_fd=parent_fd)
                except OSError as exc:
                    raise WorkflowError(f"cannot open journal without following links: {path}") from exc
            except OSError as exc:
                raise WorkflowError(f"cannot create journal without following links: {path}") from exc
        else:
            try:
                descriptor = os.open(path.name, base_flags, dir_fd=parent_fd)
            except OSError as exc:
                raise WorkflowError(f"cannot open journal without following links: {path}") from exc

        _validate_open_file(descriptor, path, single_link=single_link)
        fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            _validate_open_file(descriptor, path, single_link=single_link)
            yield descriptor, created
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        if descriptor is not None:
            if created:
                try:
                    os.fsync(descriptor)
                except OSError:
                    pass
            os.close(descriptor)
        if created:
            os.fsync(parent_fd)
        os.close(parent_fd)


def read_locked_bytes(descriptor: int, path: Path, *, max_bytes: int) -> bytes:
    """Read a bounded stable snapshot from an already locked descriptor."""
    if max_bytes < 0:
        raise WorkflowError("journal max_bytes must be non-negative")
    before = _validate_open_file(descriptor, path, single_link=True)
    if before.st_size > max_bytes:
        raise WorkflowError(f"journal exceeds size limit: {path}")
    os.lseek(descriptor, 0, os.SEEK_SET)
    data = bytearray()
    while True:
        chunk = os.read(descriptor, min(_READ_CHUNK, max_bytes - len(data) + 1))
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise WorkflowError(f"journal exceeds size limit: {path}")
    after = _validate_open_file(descriptor, path, single_link=True)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if identity_before != identity_after or len(data) != after.st_size:
        raise WorkflowError(f"journal changed during read: {path}")
    return bytes(data)


def read_bytes(
    path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_JOURNAL_BYTES,
    missing_ok: bool = False,
) -> bytes:
    """Read one locked, stable journal snapshot."""
    try:
        with locked_file(path, exclusive=False) as (descriptor, _created):
            return read_locked_bytes(descriptor, Path(path), max_bytes=max_bytes)
    except WorkflowError as exc:
        if missing_ok and isinstance(exc.__cause__, FileNotFoundError):
            return b""
        if missing_ok and not Path(path).exists() and not Path(path).is_symlink():
            return b""
        raise


def decode_jsonl(
    data: bytes,
    *,
    path: Path,
    validator: Callable[[object, int], T],
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    max_records: int | None = None,
    require_trailing_newline: bool = True,
    sequence_field: str | None = None,
) -> list[T]:
    """Decode strict JSONL and delegate record semantics to ``validator``.

    Blank lines, truncated final records, oversized records, invalid UTF-8, and
    non-JSON input fail closed. The validator receives the decoded object and
    its one-based line/sequence position.
    """
    if require_trailing_newline and data and not data.endswith(b"\n"):
        raise WorkflowError(f"journal is truncated: {path}")
    values: list[T] = []
    for line_number, raw in enumerate(data.splitlines(), start=1):
        if not raw:
            raise WorkflowError(f"journal contains an empty record at line {line_number}: {path}")
        if len(raw) > max_record_bytes:
            raise WorkflowError(f"journal record exceeds size limit at line {line_number}: {path}")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"invalid journal JSON at line {line_number}: {path}") from exc
        if sequence_field is not None:
            if not isinstance(decoded, dict) or decoded.get(sequence_field) != line_number:
                observed = decoded.get(sequence_field) if isinstance(decoded, dict) else None
                raise WorkflowError(
                    f"journal sequence mismatch at line {line_number}: "
                    f"expected {line_number}, got {observed!r}: {path}"
                )
        values.append(validator(decoded, line_number))
        if max_records is not None and len(values) > max_records:
            raise WorkflowError(f"journal exceeds record limit: {path}")
    return values


def read_jsonl(
    path: Path,
    *,
    validator: Callable[[object, int], T],
    max_bytes: int = DEFAULT_MAX_JOURNAL_BYTES,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    max_records: int | None = None,
    missing_ok: bool = False,
    require_trailing_newline: bool = True,
    sequence_field: str | None = None,
) -> list[T]:
    data = read_bytes(path, max_bytes=max_bytes, missing_ok=missing_ok)
    return decode_jsonl(
        data,
        path=Path(path),
        validator=validator,
        max_record_bytes=max_record_bytes,
        max_records=max_records,
        require_trailing_newline=require_trailing_newline,
        sequence_field=sequence_field,
    )


def _write_all(descriptor: int, data: bytes, *, path: Path) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:
            raise WorkflowError(f"short write while appending journal: {path}")
        offset += written


def transact_jsonl(
    path: Path,
    *,
    validator: Callable[[object, int], T],
    transaction: Callable[[list[T]], JournalTransactionResult[T]],
    max_bytes: int = DEFAULT_MAX_JOURNAL_BYTES,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    max_records: int | None = None,
    create_parent: bool = True,
    require_trailing_newline: bool = True,
    sequence_field: str | None = None,
) -> T:
    """Run one read/validate/optional-append transaction under an EX lock."""
    path = Path(path)
    with locked_file(
        path,
        exclusive=True,
        create=True,
        create_parent=create_parent,
    ) as (descriptor, _created):
        data = read_locked_bytes(descriptor, path, max_bytes=max_bytes)
        existing = decode_jsonl(
            data,
            path=path,
            validator=validator,
            max_record_bytes=max_record_bytes,
            max_records=max_records,
            require_trailing_newline=require_trailing_newline,
            sequence_field=sequence_field,
        )
        decision = transaction(existing)
        if decision.record is None:
            return decision.value
        encoded = canonical_json_line(decision.record)
        if len(encoded) > max_record_bytes:
            raise JournalCapacityError(f"journal record exceeds size limit: {path}")
        if len(data) + len(encoded) > max_bytes:
            raise JournalCapacityError(f"journal exceeds size limit: {path}")
        if max_records is not None and len(existing) + 1 > max_records:
            raise JournalCapacityError(f"journal exceeds record limit: {path}")
        os.lseek(descriptor, 0, os.SEEK_END)
        _write_all(descriptor, encoded, path=path)
        os.fsync(descriptor)
        return decision.value


def append_jsonl(
    path: Path,
    record: Mapping[str, Any],
    *,
    validator: Callable[[object, int], T],
    max_bytes: int = DEFAULT_MAX_JOURNAL_BYTES,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
    max_records: int | None = None,
    sequence_field: str | None = None,
) -> T:
    """Append one record whose sequence/semantics are validated by position."""
    def decide(existing: list[T]) -> JournalTransactionResult[T]:
        value = validator(dict(record), len(existing) + 1)
        return JournalTransactionResult(value=value, record=dict(record))

    return transact_jsonl(
        path,
        validator=validator,
        transaction=decide,
        max_bytes=max_bytes,
        max_record_bytes=max_record_bytes,
        max_records=max_records,
        sequence_field=sequence_field,
    )
