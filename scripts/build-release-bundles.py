#!/usr/bin/env python3
"""Build reproducible platform-labelled release installer bundles."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
import tarfile
import tempfile
from pathlib import Path


PLATFORMS = ("linux", "wsl2", "macos")
REQUIRED_FILES = (
    "install.sh",
    "uninstall.sh",
    "scripts/install-source.sh",
    "scripts/configure-hooks.py",
    "bin/agent-workflow",
    "config/agent-workflow.example.toml",
)
REQUIRED_TREES = ("schemas", "evals", "prompt-packs", "docs/man", "skills", "scripts/hooks")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def copy_release_surface(root: Path, destination: Path) -> None:
    for relative in REQUIRED_FILES:
        source = root / relative
        if not source.is_file():
            raise SystemExit(f"missing release bundle file: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for relative in REQUIRED_TREES:
        source = root / relative
        if not source.is_dir():
            raise SystemExit(f"missing release bundle tree: {relative}")
        shutil.copytree(source, destination / relative, copy_function=shutil.copy2)


def add_reproducible(tar: tarfile.TarFile, path: Path, archive_root: Path) -> None:
    for child in sorted(path.iterdir(), key=lambda item: item.name):
        relative = child.relative_to(archive_root)
        info = tar.gettarinfo(str(child), arcname=str(relative))
        info.mtime = 0
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        if child.is_file():
            with child.open("rb") as stream:
                tar.addfile(info, stream)
        else:
            tar.addfile(info)
            add_reproducible(tar, child, archive_root)


def build_bundle(root: Path, wheel: Path, version: str, platform: str, output: Path) -> Path:
    bundle_name = f"agent-workflow-{version}-{platform}"
    with tempfile.TemporaryDirectory(prefix="agent-workflow-bundle-") as temporary:
        staging = Path(temporary) / bundle_name
        staging.mkdir()
        copy_release_surface(root, staging)
        shutil.copy2(wheel, staging / wheel.name)
        (staging / ".release-bundle").write_text(f"{version}\n{platform}\n", encoding="utf-8")
        for path in staging.rglob("*"):
            os.utime(path, (0, 0), follow_symlinks=False)
        output.mkdir(parents=True, exist_ok=True)
        archive = output / f"{bundle_name}.tar.gz"
        with archive.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as tar:
                    add_reproducible(tar, staging, staging.parent)
        return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--version", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    version = args.version.removeprefix("v")
    if not version or any(character not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-" for character in version):
        raise SystemExit("version must be an immutable tag-compatible value")
    if not args.wheel.is_file() or not args.sdist.is_file():
        raise SystemExit("wheel and sdist inputs must be regular files")
    for platform in PLATFORMS:
        build_bundle(args.root, args.wheel, version, platform, args.output_dir)
    print(f"release bundles: {len(PLATFORMS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
