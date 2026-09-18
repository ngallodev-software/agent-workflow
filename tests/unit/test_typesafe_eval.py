from agent_workflow.typesafe_eval import (
    EvalFeature,
    FeatureRegistry,
    OutcomeJoiner,
    comparison_report,
    make_observation,
)


def test_feature_registry_is_explicit_and_duplicate_safe():
    registry = FeatureRegistry()
    feature = EvalFeature("routing-advice/v1", {}, {}, {}, {}, ("accuracy",), {})
    registry.register(feature)
    assert registry.records()[0]["schema"] == "agent-workflow-typesafe/eval-feature/v1"
    try:
        registry.register(feature)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate feature was accepted")


def test_shadow_observation_and_immutable_join_report():
    obs = make_observation(
        feature_id="routing-advice/v1", mode="shadow-normal-usage",
        identity={"dataset_version": "synthetic-1"}, source_input={"task": "x"},
        projected_input={"task": "x"}, control=lambda: {"route": "implementation"},
        candidate=lambda: {"route": "review"}, observation_id="obs-1",
    )
    joiner = OutcomeJoiner()
    outcome = joiner.join("obs-1", "static-oracle", {"oracle": {"route": "implementation"}})
    assert joiner.join("obs-1", "static-oracle", {"oracle": {"route": "implementation"}}) == outcome
    report = comparison_report([obs], [outcome])
    assert report["correctness"] == {"control_only": 1, "candidate_only": 0, "both_correct": 0, "both_wrong": 0}
    assert obs["comparison"]["candidate_applied"] is False
