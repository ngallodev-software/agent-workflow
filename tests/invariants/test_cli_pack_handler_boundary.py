from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import agent_workflow.cli_handlers.pack as handler
from agent_workflow.config import defaults


def test_pack_scaffold_checksum_and_archive_forward_exact_arguments(
    tmp_path: Path, monkeypatch
) -> None:
    settings = defaults(tmp_path / "config.toml")
    calls = []
    monkeypatch.setattr(
        handler,
        "scaffold_pack",
        lambda destination, phases, name: calls.append(
            ("scaffold", destination, phases, name)
        ) or {"scaffold": True},
    )
    monkeypatch.setattr(handler, "absolute_path", lambda path: Path("/absolute") / path.name)
    monkeypatch.setattr(
        handler,
        "write_checksum_manifest",
        lambda source: calls.append(("checksum", source)) or source / "MANIFEST.sha256",
    )
    monkeypatch.setattr(
        handler,
        "archive_pack",
        lambda received_settings, source, output: calls.append(
            ("archive", received_settings, source, output)
        ) or {"archive": True},
    )

    data, exit_code = handler.handle_pack_command(
        settings,
        Namespace(pack_command="scaffold", destination=tmp_path / "pack", phases=4, name="Pack"),
    )
    assert (data, exit_code) == ({"scaffold": True}, None)

    data, exit_code = handler.handle_pack_command(
        settings, Namespace(pack_command="checksum", source=tmp_path / "source")
    )
    assert data == {"manifest": "/absolute/source/MANIFEST.sha256"}
    assert exit_code is None

    data, exit_code = handler.handle_pack_command(
        settings,
        Namespace(pack_command="archive", source=tmp_path / "source", output=tmp_path / "pack.tar.zst"),
    )
    assert (data, exit_code) == ({"archive": True}, None)
    assert calls == [
        ("scaffold", tmp_path / "pack", 4, "Pack"),
        ("checksum", Path("/absolute/source")),
        ("archive", settings, tmp_path / "source", tmp_path / "pack.tar.zst"),
    ]


def test_pack_validate_handler_owns_output_and_exit_status(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    settings = defaults(tmp_path / "config.toml")
    report = SimpleNamespace(
        root=tmp_path / "pack",
        phases=2,
        tasks=3,
        ok=False,
        warnings=("old field",),
        errors=("missing task",),
        as_dict=lambda: {"ok": False},
    )
    monkeypatch.setattr(handler, "absolute_path", lambda path: path.resolve())
    monkeypatch.setattr(handler, "validate_pack", lambda source, verify_checksums: report)

    data, exit_code = handler.handle_pack_command(
        settings,
        Namespace(
            pack_command="validate",
            source=tmp_path / "pack",
            verify_checksums=True,
            json=False,
        ),
    )
    captured = capsys.readouterr()
    assert data is None
    assert exit_code == 1
    assert f"pack: {report.root}" in captured.out
    assert "phases: 2; tasks: 3; valid: False" in captured.out
    assert "warning: old field" in captured.out
    assert "error: missing task" in captured.err


def test_pack_validate_json_output_is_complete(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    settings = defaults(tmp_path / "config.toml")
    report = SimpleNamespace(
        root=tmp_path / "pack", phases=1, tasks=1, ok=True, warnings=(), errors=(),
        as_dict=lambda: {"ok": True, "tasks": 1},
    )
    monkeypatch.setattr(handler, "absolute_path", lambda path: path)
    monkeypatch.setattr(handler, "validate_pack", lambda source, verify_checksums: report)

    data, exit_code = handler.handle_pack_command(
        settings,
        Namespace(pack_command="validate", source=tmp_path / "pack", verify_checksums=False, json=True),
    )
    assert data is None
    assert exit_code == 0
    assert capsys.readouterr().out == '{\n  "ok": true,\n  "tasks": 1\n}\n'
