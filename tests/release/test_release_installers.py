from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tarfile
from pathlib import Path

from tests.conftest import REPO_ROOT


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fake_release(root: Path, *, bad_checksum: bool = False) -> tuple[Path, Path]:
    release = root / "release"
    release.mkdir()
    bundle_name = "agent-workflow-0.7.5-linux.tar.gz"
    wheel_name = "agent_workflow-0.7.5-py3-none-any.whl"
    staging = root / "agent-workflow-0.7.5-linux"
    staging.mkdir()
    (staging / "install.sh").write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$AGENT_WORKFLOW_BOOTSTRAP_TEST_MARKER\"\n",
        encoding="utf-8",
    )
    wheel = staging / wheel_name
    wheel.write_bytes(b"fake wheel")
    with tarfile.open(release / bundle_name, "w:gz") as archive:
        archive.add(staging, arcname=staging.name)
    manifest = release / "SHA256SUMS"
    bundle_digest = "0" * 64 if bad_checksum else _sha256(release / bundle_name)
    manifest.write_text(
        f"{bundle_digest}  {bundle_name}\n{_sha256(wheel)}  {wheel_name}\n",
        encoding="utf-8",
    )
    return release, wheel


def _run_bootstrap(release: Path, *args: str, marker: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "AGENT_WORKFLOW_RELEASE_BASE_URL": release.as_uri(),
            "AGENT_WORKFLOW_BOOTSTRAP_TEST_MARKER": str(marker),
        }
    )
    return subprocess.run(
        ["/bin/sh", "-s", "--", *args],
        cwd=REPO_ROOT,
        env=env,
        input=(REPO_ROOT / "install.sh").read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_bootstrap_selects_tagged_bundle_and_verifies_checksum_offline(tmp_path: Path) -> None:
    release, _ = _write_fake_release(tmp_path)
    marker = tmp_path / "marker"
    result = _run_bootstrap(release, "--version", "v0.7.5", "--python", sys.executable, marker=marker)
    assert result.returncode == 0, result.stdout + result.stderr
    marker_args = marker.read_text(encoding="utf-8").splitlines()
    assert marker_args[-2] == "--wheel"
    assert Path(marker_args[-1]).name == "agent_workflow-0.7.5-py3-none-any.whl"


def test_bootstrap_stops_before_install_on_checksum_failure(tmp_path: Path) -> None:
    release, _ = _write_fake_release(tmp_path, bad_checksum=True)
    marker = tmp_path / "marker"
    result = _run_bootstrap(release, "--version", "v0.7.5", "--python", sys.executable, marker=marker)
    assert result.returncode != 0
    assert "checksum" in result.stderr.lower()
    assert not marker.exists()


def test_bootstrap_rejects_unsupported_host_before_download(tmp_path: Path) -> None:
    release, _ = _write_fake_release(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        "#!/bin/sh\nif [ \"${1:-}\" = -m ]; then printf 'x86_64\\n'; else printf 'Plan9\\n'; fi\n",
        encoding="utf-8",
    )
    (fake_bin / "uname").chmod(0o755)
    env = os.environ.copy()
    env.update({"PATH": f"{fake_bin}:/usr/bin:/bin", "AGENT_WORKFLOW_RELEASE_BASE_URL": release.as_uri()})
    result = subprocess.run(
        ["/bin/sh", "-s", "--", "--version", "v0.7.5"],
        cwd=REPO_ROOT,
        env=env,
        input=(REPO_ROOT / "install.sh").read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "unsupported operating system" in result.stderr


def test_release_workflow_is_tag_only_and_bundle_builder_is_reproducible(tmp_path: Path) -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "pull_request" not in workflow
    assert 'tags:' in workflow
    assert "gh release create \"$RELEASE_TAG\"" in workflow

    wheel = tmp_path / "agent_workflow-0.7.5-py3-none-any.whl"
    sdist = tmp_path / "agent_workflow-0.7.5.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    output = tmp_path / "dist"
    command = [
        sys.executable,
        "scripts/build-release-bundles.py",
        "--root",
        str(REPO_ROOT),
        "--version",
        "v0.7.5",
        "--wheel",
        str(wheel),
        "--sdist",
        str(sdist),
        "--output-dir",
        str(output),
    ]
    subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    first = {path.name: path.read_bytes() for path in output.glob("agent-workflow-*.tar.gz")}
    subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    second = {path.name: path.read_bytes() for path in output.glob("agent-workflow-*.tar.gz")}
    assert first == second
    assert set(first) == {
        "agent-workflow-0.7.5-linux.tar.gz",
        "agent-workflow-0.7.5-wsl2.tar.gz",
        "agent-workflow-0.7.5-macos.tar.gz",
    }
    with tarfile.open(output / "agent-workflow-0.7.5-macos.tar.gz", "r:gz") as archive:
        names = set(archive.getnames())
    assert "agent-workflow-0.7.5-macos/install.sh" in names
    assert "agent-workflow-0.7.5-macos/uninstall.sh" in names
    assert "agent-workflow-0.7.5-macos/agent_workflow-0.7.5-py3-none-any.whl" in names
