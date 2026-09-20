from agent_workflow.decisions import DECISIONS


def test_registered_runtime_decisions_match_live_routing_boundary() -> None:
    """Do not advertise benchmark/advisory questions as live host decisions."""
    assert set(DECISIONS) == {
        "routing.task_class",
        "routing.interaction_required",
        "routing.semantic_risk",
    }
