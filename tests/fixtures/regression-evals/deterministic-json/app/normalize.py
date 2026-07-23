"""Deterministic normalization target used by the receipt-backed regression eval."""
from __future__ import annotations

from typing import Any, Iterable


def normalize_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return unique records normalized by case-folded id and stable key order.

    The last record for a normalized id wins. Input objects are never mutated.
    """
    normalized: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("each record must be an object")
        raw_id = record.get("id")
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValueError("record id must be a non-empty string")
        key = raw_id.strip().casefold()
        clean = {str(name): value for name, value in record.items()}
        clean["id"] = key
        normalized[key] = dict(sorted(clean.items()))
    return [normalized[key] for key in sorted(normalized)]
