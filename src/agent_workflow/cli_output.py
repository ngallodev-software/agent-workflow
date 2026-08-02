"""Shared terminal rendering helpers for CLI command-domain handlers."""

from __future__ import annotations

import json
from typing import Any


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def print_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
) -> None:
    if not rows:
        print("No records.")
        return
    widths = {key: len(title) for key, title in columns}
    for row in rows:
        for key, _ in columns:
            widths[key] = max(widths[key], len(str(row.get(key, ""))))
    print("  ".join(title.ljust(widths[key]) for key, title in columns))
    print("  ".join("-" * widths[key] for key, _ in columns))
    for row in rows:
        print("  ".join(str(row.get(key, "")).ljust(widths[key]) for key, _ in columns))


def print_mapping(data: dict[str, Any]) -> None:
    for key, value in data.items():
        if key == "capture" and value:
            print("--- terminal capture ---")
            print(str(value).rstrip())
        elif isinstance(value, (dict, list)):
            print(f"{key}: {json.dumps(value, sort_keys=True)}")
        else:
            print(f"{key}: {value}")
