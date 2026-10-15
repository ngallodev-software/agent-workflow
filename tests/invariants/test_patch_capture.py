from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow import run_collections, terminal_pipeline
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.finalization import finalize_run
from agent_workflow.process import run_bytes
from agent_workflow.receipts import seal_run, verify_seal_details
from agent_workflow.run_collections import capture_patch
from agent_workflow.run_lifecycle import initialize_execution_path, transition_execution_path
from agent_workflow.terminal_pipeline import TerminalObservation, finalize_terminal_run
from tests.conftest import git_repo
from tests.support import write_minimal_run


def _fixture(tmp_path: Path):
    repo = tmp_path / 'repo'
    base = git_repo(repo)
    run = tmp_path / 'state' / 'runs' / 'test-run'
    write_minimal_run(run)
    baseline = json.loads((run / 'source-baseline.json').read_text())
    baseline['components']['primary'].update(path=str(repo), head=base)
    (run / 'source-baseline.json').write_text(json.dumps(baseline))
    launch = json.loads((run / 'agent-run-contract.json').read_text())
    launch['worktree'].update(path=str(repo), source_revision=base)
    launch['paths']['workdir'] = str(repo)
    launch['source_baseline']['sha256'] = hashlib.sha256((run / 'source-baseline.json').read_bytes()).hexdigest()
    (run / 'agent-run-contract.json').write_text(json.dumps(launch))
    initialize_execution_path(run / 'status.json', json.loads((run / 'status.json').read_text()))
    transition_execution_path(run / 'status.json', 'running', actor='test', reason='fixture started')
    return repo, run, base, launch


def _git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout


@pytest.mark.parametrize('kind', ['empty', 'text', 'binary'])
def test_patch_bytes_and_external_helpers(tmp_path, monkeypatch, kind):
    repo, run, base, _ = _fixture(tmp_path)
    if kind != 'empty':
        (repo / 'README.md').write_bytes(b'after\x00\xff\n' if kind == 'binary' else b'changed\n')
        _git(repo, 'add', 'README.md')
        _git(repo, 'commit', '-qm', 'change')
    sentinel = tmp_path / 'helper-called'
    helper = tmp_path / 'helper'
    helper.write_text(f'#!/bin/sh\ntouch {sentinel}\nexit 1\n')
    helper.chmod(0o755)
    _git(repo, 'config', 'diff.external', str(helper))
    _git(repo, 'config', 'diff.fixture.textconv', str(helper))
    (repo / '.git' / 'info' / 'attributes').write_text('README.md diff=fixture\n')
    monkeypatch.setenv('GIT_EXTERNAL_DIFF', '/nonexistent/worker-helper')
    if kind != 'empty':
        # Exact EVIDENCE-001 reproduction: controlled environment sets an empty
        # helper, and Git exits 128 rather than producing the changed patch.
        broken = run_bytes(['git', '-C', str(repo), 'diff', '--binary', base], check=False)
        assert broken.returncode == 128
        assert b'cannot run : No such file or directory' in broken.stderr
    capture_patch(repo, run, run / 'patch.diff')
    expected = _git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--no-color', '--binary', '--full-index', base, '--')
    assert (run / 'patch.diff').read_bytes() == expected
    assert bool(expected) == (kind != 'empty')
    if kind == 'binary':
        assert b'GIT binary patch' in expected
        _git(repo, 'worktree', 'add', '--detach', str(tmp_path / 'replay'), base)
        _git(tmp_path / 'replay', 'apply', str(run / 'patch.diff'))
        assert (tmp_path / 'replay' / 'README.md').read_bytes() == (repo / 'README.md').read_bytes()
    assert not sentinel.exists()


def test_untracked_binary_and_aggregate_bound(tmp_path, monkeypatch):
    repo, run, _, _ = _fixture(tmp_path)
    (repo / 'one.bin').write_bytes(b'\0\xff' * 50)
    capture_patch(repo, run, run / 'patch.diff')
    one = (run / 'patch.diff').read_bytes()
    assert b'GIT binary patch' in one
    (repo / 'two.bin').write_bytes(b'\0\xfe' * 50)
    monkeypatch.setattr(run_collections, 'MAX_PATCH_BYTES', len(one) + 10)
    with pytest.raises(WorkflowError, match='combined output exceeds'):
        capture_patch(repo, run, run / 'patch.diff')
    assert not (run / 'patch.diff').exists()


@pytest.mark.parametrize('stage', ['diff', 'ls-files', '--no-index'])
@pytest.mark.parametrize('failure', ['exit', 'stdout', 'stderr', 'timeout', 'cancelled'])
def test_every_git_stage_rejects_failure_and_incomplete_output(tmp_path, monkeypatch, stage, failure):
    repo, run, _, _ = _fixture(tmp_path)
    (repo / 'untracked').write_text('addition\n')
    real = run_collections.run_bytes

    def failed(argv, **kwargs):
        result = real(argv, **kwargs)
        selected = ('--no-index' in argv if stage == '--no-index' else
                    argv[3] == stage and '--no-index' not in argv)
        if selected:
            changes = {'exit': {'returncode': 128, 'stderr': b'fatal: injected Git failure'},
                       'stdout': {'stdout_truncated': True},
                       'stderr': {'stderr_truncated': True},
                       'timeout': {'timed_out': True},
                       'cancelled': {'cancelled': True}}[failure]
            return replace(result, **changes)
        return result

    monkeypatch.setattr(run_collections, 'run_bytes', failed)
    with pytest.raises(WorkflowError, match='patch capture git') as error:
        capture_patch(repo, run, run / 'patch.diff')
    if failure == 'exit':
        assert 'fatal: injected Git failure' in str(error.value)
    assert not (run / 'patch.diff').exists()  # no old, empty, or partial success artifact


def test_real_git_failure_and_missing_baseline(tmp_path):
    repo, run, _, _ = _fixture(tmp_path)
    baseline = json.loads((run / 'source-baseline.json').read_text())
    baseline['components']['primary']['head'] = '0' * 40
    (run / 'source-baseline.json').write_text(json.dumps(baseline))
    with pytest.raises(WorkflowError, match='exit=128.*fatal: bad object'):
        capture_patch(repo, run, run / 'patch.diff')
    (run / 'source-baseline.json').unlink()
    with pytest.raises(WorkflowError):
        capture_patch(repo, run, run / 'patch.diff')
    assert not (run / 'patch.diff').exists()


@pytest.mark.parametrize('recovery', [False, True])
@pytest.mark.parametrize('failure', [False, True])
def test_terminal_and_recovery_share_patch_success_and_failure(tmp_path, monkeypatch, recovery, failure):
    repo, run, base, launch = _fixture(tmp_path)
    (repo / 'README.md').write_bytes(b'changed\0\xff\n')
    _git(repo, 'add', 'README.md')
    _git(repo, 'commit', '-qm', 'change')
    # Isolate patch collection from worker handoff validation; all terminal
    # policy/status/sealing machinery and the recovery entry point are real.
    monkeypatch.setattr(terminal_pipeline, 'collect_completion', lambda *a, **k: {'validation_status': 'valid'})
    if failure:
        baseline = json.loads((run / 'source-baseline.json').read_text())
        baseline['components']['primary']['head'] = '0' * 40
        (run / 'source-baseline.json').write_text(json.dumps(baseline))
    if recovery:
        # Recovery uses the existing public dead-orphan observation; it must
        # not fabricate process success. Here only patch/sealing is under test.
        settings = defaults(tmp_path / 'config.toml')
        object.__setattr__(settings, 'state_root', tmp_path / 'state')
        operation = lambda: finalize_run(settings, 'test-run', observation={'observed_state': 'orphaned', 'worker_alive': False})
    else:
        operation = lambda: finalize_terminal_run(run, launch, TerminalObservation(executor_result='completed', exit_code=0))
    if failure:
        with pytest.raises(WorkflowError, match='missing artifacts.*patch.diff'):
            operation()
        final = json.loads((run / 'final-status.json').read_text())
        assert final['status'] == 'failed' and final['acceptance_eligible'] is False
        assert any('exit=128' in error and 'bad object' in error for error in final['pump_errors'])
        assert not (run / 'patch.diff').exists()
        assert not (run / 'final-receipt.json').exists()
    else:
        operation()
        receipt, _ = verify_seal_details(run)
        expected = _git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--binary', '--full-index', base)
        patch = next(row for row in receipt['artifacts'] if row['path'] == 'patch.diff')
        assert patch['sha256'] == hashlib.sha256(expected).hexdigest()
        assert (run / 'patch.diff').read_bytes() == expected and expected
        if recovery:
            assert (run / 'recovery-finalization.json').is_file()


def test_historical_seal_is_verified_without_rewriting(tmp_path):
    _, run, _, _ = _fixture(tmp_path)
    seal_run(run, agent_run_id='test-run')  # historical empty patch remains valid
    before = {p: p.read_bytes() for p in run.rglob('*') if p.is_file()}
    with pytest.raises(WorkflowError, match='sealed run'):
        capture_patch(tmp_path, run, run / 'patch.diff')
    verify_seal_details(run)
    assert all(p.read_bytes() == data for p, data in before.items())
