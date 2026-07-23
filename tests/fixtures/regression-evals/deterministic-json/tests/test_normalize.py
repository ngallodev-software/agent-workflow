from copy import deepcopy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.normalize import normalize_records


def test_normalizes_sorts_and_deduplicates_without_mutation():
    source = [{"id": " B ", "value": 1}, {"value": 2, "id": "a"}, {"id": "b", "value": 3}]
    before = deepcopy(source)
    assert normalize_records(source) == [{"id": "a", "value": 2}, {"id": "b", "value": 3}]
    assert source == before


def test_rejects_missing_id():
    try:
        normalize_records([{"value": 1}])
    except ValueError:
        pass
    else:
        raise AssertionError("missing id must fail")
