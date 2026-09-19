from pathlib import Path

from agent_workflow.typesafe_eval_runtime import EvidenceStore, ShadowCapture, enforce_non_regression, join_delayed_outcome, reports_by_cohort, run_static


def test_sqlite_evidence_survives_restart_and_rejects_conflicts(tmp_path: Path):
    path = tmp_path / "evidence.sqlite"
    store = EvidenceStore(path)
    observations = run_static([{"case_id": "a", "dataset_version": "d1"}], feature_id="f/v1", control=lambda _: {"x": 1}, candidate=lambda _: {"x": 1}, oracle=lambda _: {"x": 1}, store=store)
    report = store.report()
    assert report["correctness"]["both_correct"] == 1
    store.close()
    reopened = EvidenceStore(path)
    assert len(reopened.observations()) == 1
    assert reopened.report()["counts"]["oracle_eligible"] == 1
    try:
        reopened.put_observation(dict(observations[0], feature_id="other"))
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting immutable evidence was accepted")


def test_shadow_capture_is_opt_in_and_redacted():
    store = EvidenceStore(":memory:")
    capture = ShadowCapture(store, enabled=False, sample_rate=1)
    assert capture.capture(feature_id="f/v1", identity={}, source_input={"secret": "x"}, projected_input={}, control=lambda: {}, candidate=lambda: {}) is None
    capture.enabled = True
    observation = capture.capture(feature_id="f/v1", identity={}, source_input={"secret": "x"}, projected_input={}, control=lambda: {}, candidate=lambda: {})
    assert observation["input"]["raw_input_persisted"] is False
    assert store.observations()[0]["privacy"]["secret_values_stored"] is False


def test_delayed_join_is_restart_safe_and_cohorts_do_not_pool(tmp_path: Path):
    path = tmp_path / "joined.sqlite"
    store = EvidenceStore(path)
    observations = run_static([{"case_id": "a", "dataset_version": "d1"}], feature_id="f/v1", control=lambda _: {"x": 1}, candidate=lambda _: {"x": 1}, oracle=lambda _: {"x": 1}, store=store)
    first = join_delayed_outcome(store, observations[0]["observation_id"], "agent-run-outcome", {"status": "completed"})
    assert join_delayed_outcome(store, observations[0]["observation_id"], "agent-run-outcome", {"status": "completed"}) == first
    store.close()
    reopened = EvidenceStore(path)
    assert len(reopened.outcomes()) == 2  # static oracle plus delayed lifecycle outcome
    assert len(reports_by_cohort(reopened)) == 1
    assert not enforce_non_regression(reopened.report(), minimum_candidate_rate=1.0)
