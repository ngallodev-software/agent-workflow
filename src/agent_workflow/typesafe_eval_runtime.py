"""Durable, opt-in host runtime for TypeSafe comparative evidence."""
from __future__ import annotations

import json
import random
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .typesafe_eval import OutcomeJoiner, comparison_report, make_observation, validate_observation


class EvidenceStore:
    """SQLite projection with immutable observation/outcome rows."""
    def __init__(self, path: str | Path) -> None:
        self.db = sqlite3.connect(str(path))
        self.db.execute("CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS outcomes (id TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(id, kind))")
        self.db.commit()

    def put_observation(self, observation: Mapping[str, Any]) -> None:
        validate_observation(observation)
        payload = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        try:
            self.db.execute("INSERT INTO observations VALUES (?, ?)", (observation["observation_id"], payload))
        except sqlite3.IntegrityError:
            old = self.db.execute("SELECT payload FROM observations WHERE id=?", (observation["observation_id"],)).fetchone()
            if old is None or old[0] != payload:
                raise ValueError("observation ID already contains different evidence")
        self.db.commit()

    def put_outcome(self, record: Mapping[str, Any]) -> None:
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        try:
            self.db.execute("INSERT INTO outcomes VALUES (?, ?, ?)", (record["observation_id"], record["outcome_kind"], payload))
        except sqlite3.IntegrityError:
            old = self.db.execute("SELECT payload FROM outcomes WHERE id=? AND kind=?", (record["observation_id"], record["outcome_kind"])).fetchone()
            if old is None or old[0] != payload:
                raise ValueError("outcome key already contains different evidence")
        self.db.commit()

    def observations(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM observations ORDER BY id")]

    def outcomes(self) -> list[dict[str, Any]]:
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM outcomes ORDER BY id, kind")]

    def report(self) -> dict[str, Any]:
        return comparison_report(self.observations(), self.outcomes())

    def close(self) -> None:
        self.db.close()


def run_static(cases: Sequence[Mapping[str, Any]], *, feature_id: str, control: Callable[[Mapping[str, Any]], Mapping[str, Any]], candidate: Callable[[Mapping[str, Any]], Mapping[str, Any]], oracle: Callable[[Mapping[str, Any]], Mapping[str, Any]], store: EvidenceStore, repetitions: int = 1) -> list[dict[str, Any]]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    result = []
    for case in cases:
        for repetition in range(repetitions):
            obs = make_observation(feature_id=feature_id, mode="static", identity={"dataset_version": case.get("dataset_version", "unknown"), "repetition": repetition}, source_input=case, projected_input=case, case_id=case.get("case_id"), control=lambda case=case: control(case), candidate=lambda case=case: candidate(case))
            store.put_observation(obs)
            from .typesafe_eval import OutcomeJoiner
            outcome = OutcomeJoiner().join(obs["observation_id"], "static-oracle", {"oracle": dict(oracle(case))})
            store.put_outcome(outcome)
            result.append(obs)
    return result


class ShadowCapture:
    def __init__(self, store: EvidenceStore, *, enabled: bool = False, sample_rate: float = 0.0, seed: int | None = None) -> None:
        if not 0 <= sample_rate <= 1:
            raise ValueError("sample_rate must be between 0 and 1")
        self.store, self.enabled, self.sample_rate = store, enabled, sample_rate
        self.random = random.Random(seed)

    def capture(self, *, feature_id: str, identity: Mapping[str, Any], source_input: Mapping[str, Any], projected_input: Mapping[str, Any], control: Callable[[], Mapping[str, Any]], candidate: Callable[[], Mapping[str, Any]] | None) -> dict[str, Any] | None:
        if not self.enabled or self.random.random() > self.sample_rate:
            return None
        observation = make_observation(feature_id=feature_id, mode="shadow-normal-usage", identity=dict(identity), source_input=source_input, projected_input=projected_input, control=control, candidate=candidate)
        self.store.put_observation(observation)
        return observation
