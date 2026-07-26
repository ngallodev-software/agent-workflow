from __future__ import annotations

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
