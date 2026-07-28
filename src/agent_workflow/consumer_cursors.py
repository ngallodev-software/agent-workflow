"""Rebuildable, per-consumer cursors for append-only source journals."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from .contracts import read_launch_contract, validate_instance
from .errors import WorkflowError
from .messages import message_digest, validate_message
from .util import atomic_write_json, fsync_directory, utc_now, validate_id


CURSOR_SCHEMA = "agent-workflow/consumer-cursor/v1"
DISPOSITION_SCHEMA = "agent-workflow/handling-disposition/v1"
CURSOR_SCHEMA_VERSION = 1
DISPOSITIONS = frozenset(
    {"applied", "rejected", "ignored", "deferred", "security_error"}
)
_PRINCIPALS = frozenset({"child", "orchestrator"})
MAX_RECONSTRUCTION_RECORDS = 100_000


class CursorIntegrityError(WorkflowError):
    """A source or cursor identity conflict that must fail closed."""


class CursorCorruptError(CursorIntegrityError):
    """A cursor projection cannot be trusted and must be reconstructed."""


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _safe_token(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise CursorIntegrityError(f"{label} must be a bounded identifier")
    if any(char in value for char in "/\\\x00"):
        raise CursorIntegrityError(f"{label} cannot contain a path separator")
    return value


def _real_regular_file(path: Path, *, label: str) -> Path:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise CursorIntegrityError(f"{label} does not exist") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise CursorIntegrityError(f"{label} must be a regular non-symlink file")
    return path


def _real_directory(path: Path, *, create: bool, label: str) -> Path:
    if create and not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise CursorIntegrityError(f"{label} does not exist") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise CursorIntegrityError(f"{label} must be a real directory")
    return path


def _source_journal_identity(path: Path) -> str:
    _real_regular_file(path, label="source journal")
    resolved = path.resolve(strict=True)
    return _digest({"schema": "agent-workflow/source-journal/v1", "path": str(resolved)})


@dataclass(frozen=True, init=False)
class ConsumerBinding:
    """Identity accepted by the cursor store, never an actor/path fragment."""

    consumer_id: str
    principal: str
    source_journal_id: str
    identity_digest: str

    def __init__(
        self,
        *,
        consumer_id: str,
        principal: str,
        source_journal_id: str,
        _trusted: bool = False,
    ) -> None:
        validate_id(consumer_id, "consumer identity")
        if principal not in _PRINCIPALS:
            raise CursorIntegrityError("consumer principal is not trusted")
        if principal == "orchestrator" and not _trusted:
            raise CursorIntegrityError("orchestrator identity requires trusted configuration")
        if not source_journal_id.startswith("sha256:"):
            raise CursorIntegrityError("source journal identity is not a digest")
        object.__setattr__(self, "consumer_id", consumer_id)
        object.__setattr__(self, "principal", principal)
        object.__setattr__(self, "source_journal_id", source_journal_id)
        object.__setattr__(
            self,
            "identity_digest",
            _digest(
                {
                    "schema": "agent-workflow/consumer-identity/v1",
                    "consumer_id": consumer_id,
                    "principal": principal,
                    "source_journal_id": source_journal_id,
                }
            ),
        )

    @classmethod
    def from_launch_contract(
        cls, contract_path: Path, *, source_journal_path: Path
    ) -> "ConsumerBinding":
        """Bind a child consumer to its immutable launch contract."""
        contract = read_launch_contract(contract_path)
        session = contract["session"]
        consumer_id = session.get("id")
        if not isinstance(consumer_id, str):
            raise CursorIntegrityError("launch contract has no consumer session identity")
        source_path = Path(source_journal_path)
        expected = contract_path.parent / "messages.jsonl"
        if source_path.resolve(strict=False) != expected.resolve(strict=False):
            raise CursorIntegrityError(
                "launch-bound child consumer may only consume its launch journal"
            )
        return cls(
            consumer_id=consumer_id,
            principal="child",
            source_journal_id=_source_journal_identity(source_path),
        )

    @classmethod
    def from_trusted_config(
        cls, config_path: Path, *, state_root: Path, source_journal_path: Path
    ) -> "ConsumerBinding":
        """Load a trusted identity file below the configured state root.

        The file is intentionally not addressable by an actor label.  Its
        location is administrator-controlled and its identity is hashed before
        it participates in any cursor filename.
        """
        root = _real_directory(Path(state_root), create=True, label="state root")
        trusted_root = _real_directory(root / "trusted-consumers", create=False, label="trusted consumer root")
        path = Path(config_path)
        try:
            path.relative_to(trusted_root)
        except ValueError as exc:
            raise CursorIntegrityError("trusted consumer config escapes state root") from exc
        _real_regular_file(path, label="trusted consumer config")
        if path.stat().st_mode & 0o022:
            raise CursorIntegrityError("trusted consumer config is writable by group or other")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CursorIntegrityError("trusted consumer config is invalid") from exc
        if not isinstance(value, dict) or value.get("schema") != "agent-workflow/trusted-consumer/v1":
            raise CursorIntegrityError("trusted consumer config has an unsupported schema")
        consumer_id = value.get("consumer_id")
        principal = value.get("principal")
        if not isinstance(consumer_id, str) or principal not in _PRINCIPALS:
            raise CursorIntegrityError("trusted consumer config has an invalid identity")
        return cls(
            consumer_id=consumer_id,
            principal=principal,
            source_journal_id=_source_journal_identity(Path(source_journal_path)),
            _trusted=True,
        )


@dataclass(frozen=True)
class DurableEffectReceipt:
    """Receipt proving that a target effect is committed and idempotency-bound."""

    receipt_id: str
    source_message_id: str
    source_message_digest: str
    effect_digest: str | None = None

    @classmethod
    def from_value(
        cls,
        value: Mapping[str, Any],
        *,
        source_message_id: str,
        source_message_digest: str,
    ) -> "DurableEffectReceipt":
        if not isinstance(value, Mapping) or value.get("committed") is not True:
            raise WorkflowError("target effect must return a committed receipt")
        receipt_id = _safe_token(value.get("receipt_id"), "target receipt ID")
        if value.get("source_message_id") != source_message_id:
            raise CursorIntegrityError("target receipt source message ID mismatch")
        if value.get("source_message_digest") != source_message_digest:
            raise CursorIntegrityError("target receipt source digest mismatch")
        effect_digest = value.get("effect_digest")
        if effect_digest is not None:
            effect_digest = _safe_token(effect_digest, "target effect digest")
        return cls(receipt_id, source_message_id, source_message_digest, effect_digest)


def validate_source_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate a bounded FIFO replay and fail on conflicting ID reuse."""
    if len(records) > MAX_RECONSTRUCTION_RECORDS:
        raise WorkflowError("source journal replay exceeds the bounded reconstruction limit")
    result: list[dict[str, Any]] = []
    by_id: dict[str, str] = {}
    for expected_sequence, raw in enumerate(records, start=1):
        if not isinstance(raw, Mapping):
            raise CursorIntegrityError("source journal record must be an object")
        record = dict(raw)
        validate_message(record, expected_sequence=expected_sequence)
        source_id = record["message_id"]
        digest = message_digest(record)
        prior = by_id.get(source_id)
        if prior is not None:
            if prior != digest:
                raise CursorIntegrityError("source message ID was reused with different bytes")
            raise CursorIntegrityError("source journal contains duplicate message ID")
        by_id[source_id] = digest
        result.append(record)
    return result


def build_disposition_evidence(
    *,
    binding: ConsumerBinding,
    source_record: Mapping[str, Any],
    disposition: str,
    target_receipt: DurableEffectReceipt,
) -> dict[str, Any]:
    validate_message(dict(source_record))
    if disposition not in DISPOSITIONS:
        raise WorkflowError(f"unknown handling disposition: {disposition}")
    digest = message_digest(dict(source_record))
    if target_receipt.source_message_id != source_record["message_id"] or target_receipt.source_message_digest != digest:
        raise CursorIntegrityError("target receipt is not bound to the source record")
    evidence = {
        "schema": DISPOSITION_SCHEMA,
        "schema_version": CURSOR_SCHEMA_VERSION,
        "consumer_id": binding.consumer_id,
        "consumer_identity_digest": binding.identity_digest,
        "source_journal_id": binding.source_journal_id,
        "source_sequence": source_record["sequence"],
        "source_message_id": source_record["message_id"],
        "source_message_digest": digest,
        "disposition": disposition,
        "target_receipt_id": target_receipt.receipt_id,
        "updated_at": utc_now(),
    }
    validate_instance(evidence, DISPOSITION_SCHEMA, artifact="handling disposition")
    return evidence


def _empty_cursor(binding: ConsumerBinding) -> dict[str, Any]:
    return {
        "schema": CURSOR_SCHEMA,
        "schema_version": CURSOR_SCHEMA_VERSION,
        "consumer_id": binding.consumer_id,
        "consumer_identity_digest": binding.identity_digest,
        "source_journal_id": binding.source_journal_id,
        "last_committed_source_sequence": 0,
        "last_committed_source_message_id": None,
        "last_committed_source_digest": None,
        "disposition": "deferred",
        "updated_at": utc_now(),
    }


def _validate_cursor(value: Any, binding: ConsumerBinding) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CursorCorruptError("consumer cursor must be a JSON object")
    try:
        validate_instance(value, CURSOR_SCHEMA, artifact="consumer cursor")
    except WorkflowError as exc:
        raise CursorCorruptError("consumer cursor failed schema validation") from exc
    expected = {
        "consumer_id": binding.consumer_id,
        "consumer_identity_digest": binding.identity_digest,
        "source_journal_id": binding.source_journal_id,
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        raise CursorIntegrityError("consumer cursor identity does not match trusted binding")
    return value


def _validate_disposition_evidence(
    raw: Mapping[str, Any], binding: ConsumerBinding
) -> dict[str, Any]:
    value = dict(raw)
    try:
        validate_instance(value, DISPOSITION_SCHEMA, artifact="handling disposition")
    except WorkflowError as exc:
        raise CursorIntegrityError("handling disposition failed schema validation") from exc
    if value["consumer_id"] != binding.consumer_id or value["consumer_identity_digest"] != binding.identity_digest or value["source_journal_id"] != binding.source_journal_id:
        raise CursorIntegrityError("handling disposition identity mismatch")
    return value


def reconstruct_cursor(
    binding: ConsumerBinding,
    source_records: Sequence[Mapping[str, Any]],
    target_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild the highest contiguous committed prefix from source/target evidence."""
    source = validate_source_records(source_records)
    by_id: dict[str, dict[str, Any]] = {}
    if len(target_evidence) > MAX_RECONSTRUCTION_RECORDS:
        raise WorkflowError("target evidence exceeds the bounded reconstruction limit")
    for raw in target_evidence:
        evidence = _validate_disposition_evidence(raw, binding)
        source_id = evidence["source_message_id"]
        prior = by_id.get(source_id)
        if prior is not None and prior["source_message_digest"] != evidence["source_message_digest"]:
            raise CursorIntegrityError("target evidence reuses a source ID with different bytes")
        by_id[source_id] = evidence

    rebuilt = _empty_cursor(binding)
    for record in source:
        evidence = by_id.get(record["message_id"])
        digest = message_digest(record)
        if evidence is None:
            break
        if evidence["source_message_digest"] != digest:
            raise CursorIntegrityError("target evidence digest conflicts with source journal")
        if evidence["source_sequence"] != record["sequence"]:
            raise CursorIntegrityError("target evidence sequence conflicts with source journal")
        rebuilt.update(
            last_committed_source_sequence=record["sequence"],
            last_committed_source_message_id=record["message_id"],
            last_committed_source_digest=digest,
            disposition=evidence["disposition"],
            updated_at=evidence["updated_at"],
        )
    validate_instance(rebuilt, CURSOR_SCHEMA, artifact="reconstructed consumer cursor")
    return rebuilt


class _LockedCursor:
    def __init__(self, store: "CursorStore") -> None:
        self.store = store

    def read(self) -> dict[str, Any] | None:
        return self.store._read_unlocked()

    def replace(self, value: Mapping[str, Any]) -> dict[str, Any]:
        cursor = _validate_cursor(dict(value), self.store.binding)
        self.store._write_unlocked(cursor)
        return cursor


class CursorStore:
    """Lock-scoped cursor reads and atomic compare/update operations."""

    def __init__(self, state_root: Path, binding: ConsumerBinding) -> None:
        self.state_root = _real_directory(Path(state_root), create=True, label="state root")
        self.binding = binding
        self.root = _real_directory(
            self.state_root / "consumer-cursors", create=True, label="consumer cursor root"
        )
        fsync_directory(self.root)
        self._key = binding.identity_digest.removeprefix("sha256:")
        self.path = self.root / f"{self._key}.json"
        self.lock_path = self.root / f".{self._key}.lock"

    @contextlib.contextmanager
    def locked(self) -> Iterator[_LockedCursor]:
        """Hold the per-identity lock across compare, target commit, and update."""
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except OSError as exc:
            raise CursorIntegrityError("cannot open consumer cursor lock") from exc
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise CursorIntegrityError("consumer cursor lock is not a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield _LockedCursor(self)
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _read_unlocked(self) -> dict[str, Any] | None:
        if not self.path.exists() and not self.path.is_symlink():
            return None
        _real_regular_file(self.path, label="consumer cursor")
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CursorCorruptError("consumer cursor is truncated or invalid") from exc
        return _validate_cursor(value, self.binding)

    def _write_unlocked(self, value: Mapping[str, Any]) -> None:
        if self.path.exists() or self.path.is_symlink():
            _real_regular_file(self.path, label="consumer cursor")
        atomic_write_json(self.path, dict(value), mode=0o600)

    def read(self) -> dict[str, Any] | None:
        with self.locked() as cursor:
            return cursor.read()

    def compare_and_update(
        self,
        *,
        expected_sequence: int,
        source_record: Mapping[str, Any],
        disposition: str,
        target_receipt: DurableEffectReceipt,
    ) -> dict[str, Any]:
        """Advance only when the expected cursor and committed receipt match."""
        record = dict(source_record)
        validate_message(record)
        if disposition not in DISPOSITIONS:
            raise WorkflowError(f"unknown handling disposition: {disposition}")
        digest = message_digest(record)
        with self.locked() as cursor:
            current = cursor.read() or _empty_cursor(self.binding)
            if current["last_committed_source_sequence"] != expected_sequence:
                raise CursorIntegrityError("consumer cursor compare failed")
            if record["sequence"] != expected_sequence + 1:
                raise CursorIntegrityError("source sequence is not the next FIFO record")
            receipt = DurableEffectReceipt.from_value(
                {
                    "committed": True,
                    "receipt_id": target_receipt.receipt_id,
                    "source_message_id": target_receipt.source_message_id,
                    "source_message_digest": target_receipt.source_message_digest,
                    "effect_digest": target_receipt.effect_digest,
                },
                source_message_id=record["message_id"],
                source_message_digest=digest,
            )
            next_cursor = _empty_cursor(self.binding)
            next_cursor.update(
                last_committed_source_sequence=record["sequence"],
                last_committed_source_message_id=record["message_id"],
                last_committed_source_digest=digest,
                disposition=disposition,
            )
            return cursor.replace(next_cursor)

    def process(
        self,
        source_record: Mapping[str, Any],
        *,
        disposition: str,
        commit_effect: Callable[[dict[str, Any], str, str], Mapping[str, Any]],
        after_target_commit: Callable[[DurableEffectReceipt], None] | None = None,
    ) -> dict[str, Any]:
        """Commit an idempotent target effect, then atomically advance the cursor.

        ``after_target_commit`` is an explicit crash-window hook used by
        acceptance tests and fault injectors.  If it raises, the target receipt
        remains durable while the cursor remains unchanged for replay.
        """
        record = dict(source_record)
        validate_message(record)
        digest = message_digest(record)
        with self.locked() as cursor:
            current = cursor.read() or _empty_cursor(self.binding)
            current_id = current["last_committed_source_message_id"]
            if current_id == record["message_id"]:
                if current["last_committed_source_digest"] != digest:
                    raise CursorIntegrityError("source message ID was reused with different bytes")
                return {"status": "duplicate", "cursor": current}
            if record["sequence"] <= current["last_committed_source_sequence"]:
                return {"status": "already_committed", "cursor": current}
            if record["sequence"] != current["last_committed_source_sequence"] + 1:
                raise CursorIntegrityError("source sequence is not the next FIFO record")
            raw_receipt = commit_effect(record, record["message_id"], digest)
            receipt = DurableEffectReceipt.from_value(
                raw_receipt,
                source_message_id=record["message_id"],
                source_message_digest=digest,
            )
            if after_target_commit is not None:
                after_target_commit(receipt)
            next_cursor = _empty_cursor(self.binding)
            next_cursor.update(
                last_committed_source_sequence=record["sequence"],
                last_committed_source_message_id=record["message_id"],
                last_committed_source_digest=digest,
                disposition=disposition,
            )
            committed = cursor.replace(next_cursor)
            return {
                "status": "advanced",
                "cursor": committed,
                "receipt": receipt,
                "disposition_evidence": build_disposition_evidence(
                    binding=self.binding,
                    source_record=record,
                    disposition=disposition,
                    target_receipt=receipt,
                ),
            }

    def read_or_reconstruct(
        self,
        source_records: Sequence[Mapping[str, Any]],
        target_evidence: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Use the projection when valid, otherwise rebuild a safe prefix."""
        rebuilt = reconstruct_cursor(self.binding, source_records, target_evidence)
        with self.locked() as cursor:
            try:
                current = cursor.read()
            except CursorCorruptError:
                current = None
            stale = current is None or (
                current["last_committed_source_sequence"]
                != rebuilt["last_committed_source_sequence"]
                or current["last_committed_source_message_id"]
                != rebuilt["last_committed_source_message_id"]
                or current["last_committed_source_digest"]
                != rebuilt["last_committed_source_digest"]
                or current["disposition"] != rebuilt["disposition"]
            )
            return cursor.replace(rebuilt) if stale else current
