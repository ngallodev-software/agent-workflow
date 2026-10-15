from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from agent_workflow.receipts import verify_seal_details
from tests.conftest import git_repo, prepare_and_start_agent_run, wait_for_status


@pytest.mark.parametrize('kind', ['empty', 'text', 'binary', 'git-failure'])
def test_normal_runner_seals_exact_patch(installed_product, product_env, fake_agent_path, tmp_path, kind):
    repo = tmp_path / 'repo'
    base = git_repo(repo)
    prompt = tmp_path / 'prompt.md'
    prompt.write_text('Produce deterministic patch evidence.\n')
    worker = tmp_path / 'patch-worker'
    change = '' if kind == 'empty' else (
        "\nPath('README.md').write_bytes(" + repr(b'after\0\xff\n' if kind == 'binary' else b'changed\n') + ")\n"
        "subprocess.run(['git', 'add', 'README.md'], check=True)\n"
        "subprocess.run(['git', 'commit', '-qm', 'fixture change'], check=True)\n"
    )
    if kind == 'git-failure':
        change += "Path('.git/index').write_bytes(b'invalid')\n"
    worker.write_text(fake_agent_path.read_text().replace(
        'prompt = sys.stdin.read()', 'prompt = sys.stdin.read()\n' + change,
    ).replace('"base_revision": head,', f'"base_revision": "{base}",').replace(
        '"changed_files": [],', '"changed_files": ' + ('[],' if kind == 'empty' else '["README.md"],'),
    ))
    worker.chmod(0o755)
    prepare_and_start_agent_run(installed_product, 'patch-run', repo, prompt, '--tier', 'low', '--', 'python3', worker, env=product_env)
    status = wait_for_status(product_env, 'patch-run')
    run = Path(product_env['XDG_STATE_HOME']) / 'agent-workflow/runs/patch-run'
    if kind == 'git-failure':
        assert status['status'] == 'failed' and status['failure_category'] == 'seal_failed'
        final = json.loads((run / 'final-status.json').read_text())
        assert final['completion_result'] == 'valid'
        assert final['acceptance_eligible'] is False
        assert any('patch capture git' in error and 'exit=128' in error for error in final['pump_errors'])
        assert not (run / 'patch.diff').exists() and not (run / 'final-receipt.json').exists()
        return
    assert status['status'] == 'completed', status
    receipt, _ = verify_seal_details(run)
    expected = subprocess.run([
        'git', '-C', str(repo), 'diff', '--no-ext-diff', '--no-textconv', '--binary', '--full-index', base,
    ], check=True, capture_output=True).stdout
    assert (run / 'patch.diff').read_bytes() == expected
    assert bool(expected) == (kind != 'empty')
    artifact = next(row for row in receipt['artifacts'] if row['path'] == 'patch.diff')
    assert artifact['sha256'] == hashlib.sha256(expected).hexdigest()
    assert artifact['size'] == len(expected)
    final = json.loads((run / 'final-status.json').read_text())
    assert not any(error.startswith('patch:') for error in final['pump_errors'])
