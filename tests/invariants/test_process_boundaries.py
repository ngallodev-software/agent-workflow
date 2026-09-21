from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from agent_workflow.process import EnvironmentPolicy, run, run_bytes


@pytest.mark.parametrize(
    ("stream", "limit"),
    (("stdout", 1024), ("stderr", 2048)),
)
def test_process_capture_is_bounded_and_marks_truncation(stream: str, limit: int) -> None:
    code = (
        "import sys; "
        "getattr(sys, 'stdout' if sys.argv[1] == 'stdout' else 'stderr').write('x' * 100000)"
    )
    result = run_bytes(
        [sys.executable, "-c", code, stream],
        check=False,
        max_stdout_bytes=limit if stream == "stdout" else 512,
        max_stderr_bytes=limit if stream == "stderr" else 512,
    )
    assert len(getattr(result, stream)) <= limit
    assert getattr(result, f"{stream}_truncated") is True


def test_process_timeout_group_outcome_and_secret_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "SYNTHETIC-SECRET-EXAMPLE"
    monkeypatch.setenv("UNALLOWLISTED_SECRET", secret)
    result = run(
        [sys.executable, "-c", "import os,sys,time; print(os.getenv('UNALLOWLISTED_SECRET')); print(sys.argv[1]); time.sleep(2)", "--secret", secret],
        environment=EnvironmentPolicy(values={"EXPLICIT_VALUE": secret}),
        secret_values=(secret,),
        timeout_seconds=0.1,
        check=False,
    )
    assert result.error_category == "timeout"
    assert result.signal is not None
    assert secret not in str(result.stdout)
    assert secret not in " ".join(result.argv)


def test_controlled_git_diff_ignores_ambient_external_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    target = repo / "example.txt"
    target.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "example.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
    target.write_text("after\n", encoding="utf-8")

    marker = tmp_path / "external-diff-ran"
    helper = tmp_path / "external-diff.sh"
    helper.write_text(
        "#!/usr/bin/env bash\nprintf x > \"$1\"\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", f"{helper} {marker}")

    result = run(
        ["git", "-C", str(repo), "diff", "HEAD", "--", "."],
        environment=EnvironmentPolicy(unsafe_inherit=True),
        check=True,
    )

    assert "example.txt" in str(result.stdout)
    assert not marker.exists()
