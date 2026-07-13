from __future__ import annotations

import ast
from typing import Any


class MiniYamlError(ValueError):
    pass


def _strip_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _split_items(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    depth = 0
    escaped = False
    for char in value:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char in "[{(":
            depth += 1
            current.append(char)
        elif char in "]})":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current or value.strip():
        parts.append("".join(current).strip())
    return parts


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        inside = value[1:-1].strip()
        return [] if not inside else [_parse_scalar(item) for item in _split_items(inside)]
    if value.startswith("{") and value.endswith("}"):
        result: dict[str, Any] = {}
        inside = value[1:-1].strip()
        if not inside:
            return result
        for item in _split_items(inside):
            key, separator, raw = item.partition(":")
            if not separator:
                raise MiniYamlError(f"invalid inline mapping item: {item!r}")
            result[key.strip()] = _parse_scalar(raw)
        return result
    if value[0:1] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise MiniYamlError(f"invalid quoted scalar: {value!r}") from exc
        return parsed
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def load_task_manifest(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    tasks: list[dict[str, Any]] = []
    in_tasks = False
    current_task: dict[str, Any] | None = None

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        cleaned = _strip_comment(raw_line).rstrip()
        if not cleaned.strip():
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        line = cleaned.strip()

        if indent == 0:
            current_task = None
            key, separator, raw_value = line.partition(":")
            if not separator:
                raise MiniYamlError(f"line {line_number}: expected key: value")
            key = key.strip()
            if key == "tasks":
                in_tasks = True
                result["tasks"] = tasks
                if raw_value.strip() not in {"", "[]"}:
                    parsed = _parse_scalar(raw_value)
                    if not isinstance(parsed, list):
                        raise MiniYamlError(f"line {line_number}: tasks must be a list")
                    tasks.extend(parsed)
                continue
            in_tasks = False
            result[key] = _parse_scalar(raw_value)
            continue

        if not in_tasks:
            raise MiniYamlError(
                f"line {line_number}: nested content is only supported under tasks"
            )

        if line.startswith("-"):
            remainder = line[1:].strip()
            if not remainder:
                current_task = {}
            elif remainder.startswith("{"):
                parsed = _parse_scalar(remainder)
                if not isinstance(parsed, dict):
                    raise MiniYamlError(
                        f"line {line_number}: task item must be a mapping"
                    )
                current_task = parsed
            else:
                key, separator, raw_value = remainder.partition(":")
                if not separator:
                    raise MiniYamlError(
                        f"line {line_number}: task item must be key: value"
                    )
                current_task = {key.strip(): _parse_scalar(raw_value)}
            tasks.append(current_task)
            continue

        if current_task is None:
            raise MiniYamlError(
                f"line {line_number}: task property without a preceding '-'"
            )
        key, separator, raw_value = line.partition(":")
        if not separator:
            raise MiniYamlError(f"line {line_number}: expected key: value")
        current_task[key.strip()] = _parse_scalar(raw_value)

    return result
