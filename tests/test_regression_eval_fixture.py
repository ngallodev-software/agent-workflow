from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from agent_workflow.eval.oracles import scan_for_leak

ROOT = Path(__file__).parent / "fixtures" / "regression-evals" / "deterministic-json"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"fixture_{path.stem}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalize_records


def _hidden_contract(fn):
    source = [
        {"id": " Z ", "nested": {"x": 1}},
        {"id": "z", "nested": {"x": 2}},
        {"id": "A", "value": 3},
    ]
    before = deepcopy(source)
    result = fn(source)
    assert result == [
        {"id": "a", "value": 3},
        {"id": "z", "nested": {"x": 2}},
    ]
    assert source == before
    return result


def test_reference_passes_hidden_contract_and_repeated_score_is_stable():
    fn = _load(ROOT / "app" / "normalize.py")
    first = _hidden_contract(fn)
    second = _hidden_contract(fn)
    assert first == second


@pytest.mark.parametrize("mutation", ["no_dedup.py", "mutates_input.py", "first_wins.py"])
def test_mutations_fail_hidden_contract(mutation):
    fn = _load(ROOT / "mutations" / mutation)
    with pytest.raises(AssertionError):
        _hidden_contract(fn)


def test_oracle_canary_is_detected_in_candidate_artifacts(tmp_path):
    canary = b"hidden-oracle-canary-94a2"
    candidate = tmp_path / "candidate.txt"
    candidate.write_bytes(b"prefix " + canary + b" suffix")
    assert scan_for_leak(canary, [candidate]) == [str(candidate)]
