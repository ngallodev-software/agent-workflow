from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from tests.acceptance.test_openspec_import_journey import (
    CHANGE, _import_fixture, _commit_all,
)


@pytest.mark.parametrize("count,fail_final", [(2, False), (3, False), (2, True)])
def test_dependent_tasks_installed_product(installed_product, product_env, tmp_path, count, fail_final):
    repo, pack, _ = _import_fixture(installed_product, product_env, tmp_path)
    tasks = repo / "openspec/changes" / CHANGE / "tasks.md"
    tasks.write_text(tasks.read_text() + "- [ ] 1.3 Expose the response through a request entry point\n")
    _commit_all(repo, "freeze third task")
    policy_path = tmp_path / "job-policy.json"
    policy = json.loads(policy_path.read_text())
    policy["scope"]["writable_paths"].append("src/server.py")
    policy_path.write_text(json.dumps(policy))
    installed_product.json("pack", "import-openspec", repo, CHANGE, pack,
                           "--job-policy", policy_path, env=product_env)
    shim = Path(product_env["PATH"].split(os.pathsep)[0]) / "openspec"
    log = tmp_path / "openspec-calls.log"
    shim.write_text(f"#!/bin/sh\nprintf called >> '{log}'\nexit 97\n")
    shim.chmod(0o755)
    python_shim = shim.parent / "python3"
    if not python_shim.exists():
        python_shim.symlink_to(installed_product.python)
    script = Path(__file__).parents[1] / "compat/openspec_dependent_qualification.py"
    result = subprocess.run([str(installed_product.python), str(script), str(installed_product.cli),
                             str(tmp_path / "qualification"), str(repo), str(pack), "--count", str(count),
                             *(["--fail-final"] if fail_final else [])], env=product_env, text=True, capture_output=True)
    (tmp_path / "qualification.stdout").write_text(result.stdout)
    (tmp_path / "qualification.stderr").write_text(result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not log.exists(), "no post-import OpenSpec calls are permitted"
