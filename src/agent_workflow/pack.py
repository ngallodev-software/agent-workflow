from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .assets import copy_asset_tree
from .config import Settings
from .errors import WorkflowError
from .manifests import validate_pack, write_checksum_manifest
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

    write_checksum_manifest(destination)
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
    source = expand_path(source)
    output = expand_path(output)
    if output.suffixes[-2:] != [".tar", ".zst"]:
        raise WorkflowError("archive output must end in .tar.zst")

    report = validate_pack(source, verify_checksums=False)
    if settings.validate_before_archive and not report.ok:
        raise WorkflowError(
            "prompt pack validation failed:\n- " + "\n- ".join(report.errors)
        )

    require_command("tar")
    require_command("zstd")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="agent-workflow-pack-") as tmp:
        staged_parent = Path(tmp)
        staged = staged_parent / source.name
        shutil.copytree(source, staged, symlinks=True)
        write_checksum_manifest(staged)
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
            "-",
            staged.name,
        ]
        zstd_command = [
            "zstd",
            f"-{settings.archive_level}",
            "--threads=0",
            "-q",
            "-o",
            str(output),
        ]
        tar_process = subprocess.Popen(tar_command, stdout=subprocess.PIPE)
        assert tar_process.stdout is not None
        zstd_process = subprocess.run(
            zstd_command,
            stdin=tar_process.stdout,
            capture_output=True,
            text=True,
            check=False,
        )
        tar_process.stdout.close()
        tar_code = tar_process.wait()
        if tar_code or zstd_process.returncode:
            output.unlink(missing_ok=True)
            raise WorkflowError(
                "archive failed: "
                f"tar={tar_code}, zstd={zstd_process.returncode}: "
                f"{zstd_process.stderr.strip()}"
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
