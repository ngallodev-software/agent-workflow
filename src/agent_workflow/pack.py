from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .assets import copy_asset_tree
from .config import Settings
from .contracts import validate_instance
from .errors import WorkflowError
from .manifests import validate_pack
from .path import absolute_path, read_inventory_file
from .process import require_command, run
from .util import expand_path, sha256_file, slug


def scaffold(
    destination: Path,
    phases: int,
    name: str | None = None,
) -> dict[str, Any]:
    destination = expand_path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise WorkflowError(f"destination is not empty: {destination}")
    if phases < 1 or phases > 20:
        raise WorkflowError("phases must be between 1 and 20")
    destination.mkdir(parents=True, exist_ok=True)
    copy_asset_tree("prompt-pack-root", destination)
    pack_name = name or destination.name
    root_replacements = {
        "{{PACK_NAME}}": pack_name,
        "{{PACK_SLUG}}": slug(pack_name),
    }
    for path in destination.rglob("*"):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for before, after in root_replacements.items():
                text = text.replace(before, after)
            path.write_text(text, encoding="utf-8")

    for number in range(phases):
        phase = destination / f"phase-{number}"
        copy_asset_tree("phase", phase)
        replacements = {
            "{{PHASE_NUMBER}}": str(number),
            "{{PHASE_NAME}}": f"phase-{number}",
            "{{PACK_SLUG}}": slug(pack_name),
        }
        for path in phase.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                for before, after in replacements.items():
                    text = text.replace(before, after)
                path.write_text(text, encoding="utf-8")
        template_ticket = (
            phase
            / "tickets"
            / "P{{PHASE_NUMBER}}-00-baseline-and-preflight.md"
        )
        actual_ticket = (
            phase / "tickets" / f"P{number}-00-baseline-and-preflight.md"
        )
        if template_ticket.exists():
            template_ticket.rename(actual_ticket)

    scripts_dir = destination / "scripts"
    if scripts_dir.is_dir():
        for script in scripts_dir.glob("*.sh"):
            script.chmod(script.stat().st_mode | 0o111)

    return {
        "destination": str(destination),
        "phases": phases,
        "name": pack_name,
    }


def archive(
    settings: Settings,
    source: Path,
    output: Path,
) -> dict[str, Any]:
    source = absolute_path(source)
    output = expand_path(output)
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise WorkflowError("archive output must end in .tar.zst")

    report = validate_pack(source, verify_checksums=False)
    if not report.ok:
        raise WorkflowError(
            "prompt pack validation failed:\n- " + "\n- ".join(report.errors)
        )

    require_command("tar")
    require_command("zstd")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="agent-workflow-pack-") as tmp:
        staged_parent = Path(tmp)
        staged = staged_parent / source.name
        staged.mkdir()
        # MANIFEST.sha256 is a mutable, ignored transfer sidecar. The archive's
        # canonical MANIFEST.json must describe the bytes actually archived.
        inventory = tuple(entry for entry in report.inventory if entry.path != "MANIFEST.sha256")
        if any(entry.path == "MANIFEST.json" for entry in inventory):
            raise WorkflowError("pack entry MANIFEST.json is reserved for archive integrity")
        for entry in inventory:
            target = staged / entry.path
            if entry.kind == "directory":
                target.mkdir(parents=True, exist_ok=True)
                target.chmod(0o755)
        for entry in inventory:
            if entry.kind != "file":
                continue
            target = staged / entry.path
            target.parent.mkdir(parents=True, exist_ok=True)
            read = read_inventory_file(source, entry)
            target.write_bytes(read.data)
            target.chmod(0o644)
        canonical_manifest = {
            "schema": "agent-workflow/pack-manifest/v1",
            "mode_policy": {"directory": "0755", "file": "0644"},
            "entries": [
                {
                    "type": entry.kind,
                    "path": entry.path,
                    "size": entry.size,
                    "mode": "0755" if entry.kind == "directory" else "0644",
                    **({"sha256": entry.sha256} if entry.kind == "file" else {}),
                }
                for entry in inventory
            ],
        }
        validate_instance(canonical_manifest, "agent-workflow/pack-manifest/v1", artifact="archive manifest")
        (staged / "MANIFEST.json").write_text(
            json.dumps(canonical_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tar_path = staged_parent / "pack.tar"
        tar_command = [
            "tar",
            "--sort=name",
            "--mtime=@0",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "-C",
            str(staged_parent),
            "-cf",
            str(tar_path),
            staged.name,
        ]
        zstd_command = [
            "zstd",
            f"-{settings.archive_level}",
            "--threads=0",
            "-q",
            "-o", str(output), str(tar_path),
        ]
        tar_result = run(
            tar_command,
            check=False,
            timeout_seconds=300,
            max_stdout_bytes=64 * 1024,
            max_stderr_bytes=256 * 1024,
        )
        zstd_result = run(
            zstd_command,
            check=False,
            timeout_seconds=300,
            max_stdout_bytes=64 * 1024,
            max_stderr_bytes=256 * 1024,
        )
        if tar_result.returncode or zstd_result.returncode:
            output.unlink(missing_ok=True)
            raise WorkflowError(
                "archive failed: "
                f"tar={tar_result.returncode}, zstd={zstd_result.returncode}: "
                f"{zstd_result.stderr.strip()}"
            )

    run(["zstd", "-t", "-q", str(output)])
    checksum = sha256_file(output)
    checksum_path = output.with_name(output.name + ".sha256")
    if settings.write_sha256:
        checksum_path.write_text(
            f"{checksum}  {output.name}\n", encoding="utf-8"
        )
    return {
        "source": str(source),
        "archive": str(output),
        "sha256": checksum,
        "checksum_file": (
            str(checksum_path) if settings.write_sha256 else None
        ),
        "validation": report.as_dict(),
    }
