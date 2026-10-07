from __future__ import annotations

from pathlib import Path
import subprocess

from tests.conftest import REPO_ROOT


SCRIPT = REPO_ROOT / "scripts" / "git-pull-all.sh"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_git_pull_all_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_specgen_pull_is_explicitly_opt_in() -> None:
    text = _text()
    assert "WITH_SPECGEN=0" in text
    assert "--with-specgen) WITH_SPECGEN=1" in text
    assert 'SPECGEN_SOURCE=""' in text
    assert 'if [[ "$WITH_SPECGEN" -eq 1 ]]; then' in text
    assert 'pull_repo "specgen" "$SPECGEN_SOURCE"' in text
    assert "optional and excluded unless --with-specgen is supplied." in text


def test_specgen_source_implies_specgen_pull() -> None:
    text = _text()
    block = text[text.index("--specgen-source)") : text.index("--benchmark-source)")]
    assert 'SPECGEN_SOURCE="$1"' in block
    assert "WITH_SPECGEN=1" in block
