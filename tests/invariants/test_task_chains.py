from __future__ import annotations

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.task_chains import order_tasks


def test_deterministic_topological_order():
    tasks = [{"task_id": "c", "predecessors": ["a", "b"]},
             {"task_id": "b", "predecessors": ["a"]},
             {"task_id": "a", "predecessors": []},
             {"task_id": "independent", "predecessors": []}]
    assert order_tasks(tasks) == ["a", "b", "c", "independent"]
    assert order_tasks(list(reversed(tasks))) == ["a", "b", "c", "independent"]


@pytest.mark.parametrize("tasks", [
    [{"task_id": "a", "predecessors": ["missing"]}],
    [{"task_id": "a", "predecessors": ["a"]}],
    [{"task_id": "a", "predecessors": ["b"]}, {"task_id": "b", "predecessors": ["a"]}],
    [{"task_id": "a", "predecessors": []}, {"task_id": "a", "predecessors": []}],
])
def test_invalid_dependency_graph(tasks):
    with pytest.raises(WorkflowError):
        order_tasks(tasks)
