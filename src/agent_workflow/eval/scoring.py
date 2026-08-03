from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping

from ..contracts import validate_instance, validate_launch_contract_value
from ..errors import WorkflowError
from ..evidence_repair import supplemental_repairs_for_run
from ..receipts import read_sealed_contract, read_sealed_json, verify_seal_details
from ..util import atomic_write_json
from .junit import compare_junit
from .oracles import scan_for_leak
from .scope import ScopePolicy, compare_scope

KNOWN_SCORERS = {
    "acceptance_commands",
    "completion_presence",
    "evidence_fidelity",
    "oracle_leak",
    "patch_applicability",
    "regression_guard",
    "repository_cleanliness",
    "schema_validity",
    "static_quality_delta",
    "writable_scope",
}


def _load(path: Path, *, require_read_only: bool = False) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot read evaluation receipt {path}: {exc}") from exc
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"evaluation receipt must be a regular file: {path}")
        if require_read_only and info.st_mode & 0o222:
            raise WorkflowError(f"content-addressed score receipt must be read-only: {path}")
        data = stream.read()
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read evaluation receipt {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"evaluation receipt must be an object: {path}")
    return value


def _sealed_load(
    run_dir: Path, final_receipt: Mapping[str, Any], relative_path: str
) -> dict[str, Any]:
    value, _ = read_sealed_json(run_dir, dict(final_receipt), relative_path)
    if not isinstance(value, dict):
        raise WorkflowError(f"sealed evaluation artifact must be an object: {relative_path}")
    return value


def _evidence(receipt: Mapping[str, Any], *paths: str) -> list[dict[str, str]]:
    artifacts = {
        item.get("path"): item.get("sha256")
        for item in receipt.get("artifacts", [])
        if isinstance(item, dict)
    }
    result: list[dict[str, str]] = []
    for path in paths:
        digest = artifacts.get(path)
        if not isinstance(digest, str):
            raise WorkflowError(f"score evidence is not sealed: {path}")
        result.append({"path": path, "sha256": digest})
    return result


def _receipt(
    scorer_id: str,
    final_hash: str,
    verdict: str,
    facts: dict[str, Any],
    evidence: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema": "agent-workflow/score-receipt/v1",
        "scorer": {"id": scorer_id, "version": "1"},
        "final_receipt_sha256": final_hash,
        "verdict": verdict,
        "facts": facts,
        "evidence": evidence,
    }


def _write_content_addressed(output_dir: Path, value: dict[str, Any]) -> Path:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{value['scorer']['id']}-{digest}.json"
    if path.exists() or path.is_symlink():
        if _load(path, require_read_only=True) != value:
            raise WorkflowError(f"content-addressed score receipt changed: {path}")
    else:
        atomic_write_json(path, value, mode=0o444)
    return path


def validate_score_set(
    run_dir: Path,
    value: Any,
    *,
    final_receipt: Mapping[str, Any],
    expected_final_receipt_sha256: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("score set must be an object")
    if value.get("final_receipt_sha256") != expected_final_receipt_sha256:
        raise WorkflowError("score set references a different final receipt")
    scores = value.get("scores")
    if not isinstance(scores, list) or not scores:
        raise WorkflowError("score set contains no deterministic score receipts")
    sealed = {
        item.get("path"): item.get("sha256")
        for item in final_receipt.get("artifacts", [])
        if isinstance(item, dict)
    }
    required = {"schema_validity", "completion_presence"}
    policy = evaluation_policy_for_run(run_dir, final_receipt)
    if policy:
        required.update(str(item) for item in policy.get("scorers", []))
        if policy.get("oracle_refs"):
            required.add("oracle_leak")
    expected = set(required)
    if "collections/commands-post.json" in sealed:
        expected.update({"acceptance_commands", "evidence_fidelity"})
    if {
        "collections/commands-baseline.json",
        "collections/commands-post.json",
    }.issubset(sealed):
        expected.add("regression_guard")
    if {"scope/scope-baseline.json", "scope/scope-post.json"}.issubset(sealed):
        expected.add("writable_scope")
    identifiers: list[str] = []
    for score in scores:
        validate_instance(
            score,
            "agent-workflow/score-receipt/v1",
            artifact="score receipt",
        )
        if score.get("final_receipt_sha256") != expected_final_receipt_sha256:
            raise WorkflowError("score receipt references a different final receipt")
        identifier = str(score["scorer"]["id"])
        if identifier not in KNOWN_SCORERS:
            raise WorkflowError(f"unknown scorer in score set: {identifier}")
        identifiers.append(identifier)
        for evidence in score.get("evidence", []):
            path = evidence["path"]
            if sealed.get(path) != evidence["sha256"]:
                raise WorkflowError(
                    f"score evidence is absent from the final receipt: {path}"
                )
        encoded = json.dumps(score, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(encoded).hexdigest()
        score_path = run_dir / "scores" / f"{identifier}-{digest}.json"
        try:
            stored_score = _load(score_path, require_read_only=True)
        except WorkflowError as exc:
            raise WorkflowError(
                f"content-addressed score receipt is missing or changed: {score_path}: {exc}"
            ) from exc
        if stored_score != score:
            raise WorkflowError(
                f"content-addressed score receipt is missing or changed: {score_path}"
            )
    if len(identifiers) != len(set(identifiers)):
        raise WorkflowError("score set contains duplicate scorer IDs")
    missing = sorted(required - set(identifiers))
    if missing:
        raise WorkflowError(f"score set is missing required scorers: {missing}")
    unexpected = sorted(set(identifiers) - expected)
    if unexpected:
        raise WorkflowError(f"score set contains unexpected scorers: {unexpected}")
    derived = (
        "pass"
        if all(score.get("verdict") == "pass" for score in scores)
        else "invalid"
        if any(score.get("verdict") == "invalid" for score in scores)
        else "fail"
    )
    if value.get("verdict") != derived:
        raise WorkflowError("score-set verdict contradicts score receipts")
    return value


def score_trial(
    run_dir: Path,
    *,
    output_dir: Path,
    oracle: Mapping[str, Any] | None = None,
    expected_final_receipt_sha256: str,
    oracle_canary: bytes | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    final, final_hash = verify_seal_details(
        run_dir, expected_sha256=expected_final_receipt_sha256
    )
    scores: list[dict[str, Any]] = []
    policy = evaluation_policy_for_run(run_dir, final)
    required_scorers = (
        set(policy.get("scorers", []))
        if policy
        else {
            "schema_validity",
            "acceptance_commands",
            "regression_guard",
            "writable_scope",
            "evidence_fidelity",
        }
    )
    required_scorers.update({"schema_validity", "completion_presence"})

    try:
        completion_collection, _ = read_sealed_contract(
            run_dir,
            dict(final),
            "collections/completion.json",
            "agent-workflow/completion-collection/v1",
        )
        completion_status = completion_collection.get("validation_status")
        supplemental_repairs = supplemental_repairs_for_run(run_dir, final_hash)
        scores.append(
            _receipt(
                "completion_presence",
                final_hash,
                "pass" if completion_status == "valid" else "invalid",
                {
                    "validation_status": completion_status,
                    "validation_errors": completion_collection.get("validation_errors", []),
                    "adapter": completion_collection.get("adapter"),
                    "adapter_version": completion_collection.get("adapter_version"),
                    "supplemental_repairs": supplemental_repairs,
                    "original_acceptance_authority": completion_status == "valid",
                },
                _evidence(final, "collections/completion.json"),
            )
        )
    except WorkflowError as exc:
        scores.append(
            _receipt(
                "completion_presence",
                final_hash,
                "invalid",
                {"error": str(exc), "validation_status": "unavailable"},
                [],
            )
        )

    try:
        completion, _ = read_sealed_contract(
            run_dir,
            dict(final),
            "completion.json",
            "agent-workflow/completion/v1",
        )
        read_sealed_contract(
            run_dir,
            dict(final),
            "run-provenance.json",
            "agent-workflow/run-provenance/v1",
        )
        schema_verdict = "pass"
        schema_facts: dict[str, Any] = {"contracts": ["completion", "provenance"]}
    except WorkflowError as exc:
        completion = {}
        schema_verdict = "invalid"
        schema_facts = {"error": str(exc)}
    scores.append(
        _receipt(
            "schema_validity",
            final_hash,
            schema_verdict,
            schema_facts,
            _evidence(final, "completion.json", "run-provenance.json"),
        )
    )

    post_commands_path = run_dir / "collections" / "commands-post.json"
    if post_commands_path.is_file():
        post = _sealed_load(run_dir, final, "collections/commands-post.json")
        commands = post.get("commands", [])
        failed = sorted(
            str(item.get("id"))
            for item in commands
            if not isinstance(item, dict)
            or item.get("exit_code") != 0
            or item.get("timed_out") is True
        )
        scores.append(
            _receipt(
                "acceptance_commands",
                final_hash,
                "pass" if not failed else "fail",
                {"command_count": len(commands), "failed": failed},
                _evidence(final, "collections/commands-post.json"),
            )
        )

        actual = {
            (tuple(item.get("argv", [])), item.get("cwd"), item.get("exit_code"))
            for item in commands
            if isinstance(item, dict)
        }
        claims = completion.get("commands", []) if isinstance(completion, dict) else []
        contradictions = [
            claim
            for claim in claims
            if isinstance(claim, dict)
            and (
                tuple(claim.get("argv", [])),
                claim.get("cwd"),
                claim.get("exit_code"),
            )
            not in actual
        ]
        scores.append(
            _receipt(
                "evidence_fidelity",
                final_hash,
                "pass" if not contradictions else "fail",
                {
                    "claim_count": len(claims),
                    "contradiction_count": len(contradictions),
                },
                _evidence(final, "completion.json", "collections/commands-post.json"),
            )
        )

    baseline_commands_path = run_dir / "collections" / "commands-baseline.json"
    if baseline_commands_path.is_file() and post_commands_path.is_file():
        baseline = _sealed_load(run_dir, final, "collections/commands-baseline.json")
        post = _sealed_load(run_dir, final, "collections/commands-post.json")
        regressions: list[str] = []
        fixes: list[str] = []
        baseline_by_id = {item["id"]: item for item in baseline.get("commands", [])}
        for item in post.get("commands", []):
            prior = baseline_by_id.get(item.get("id"), {})
            prior_junit = prior.get("junit")
            post_junit = item.get("junit")
            if isinstance(prior_junit, dict) and isinstance(post_junit, dict):
                if "tests" in prior_junit and "tests" in post_junit:
                    comparison = compare_junit(prior_junit["tests"], post_junit["tests"])
                    regressions.extend(comparison["regressions"])
                    fixes.extend(comparison["fixes"])
            elif prior.get("exit_code") == 0 and item.get("exit_code") != 0:
                regressions.append(str(item.get("id")))
        scores.append(
            _receipt(
                "regression_guard",
                final_hash,
                "pass" if not regressions else "fail",
                {"regressions": sorted(regressions), "fixes": sorted(fixes)},
                _evidence(
                    final,
                    "collections/commands-baseline.json",
                    "collections/commands-post.json",
                ),
            )
        )

    baseline_scope_path = run_dir / "scope" / "scope-baseline.json"
    post_scope_path = run_dir / "scope" / "scope-post.json"
    if baseline_scope_path.is_file() and post_scope_path.is_file():
        baseline_scope = _sealed_load(run_dir, final, "scope/scope-baseline.json")
        post_scope = _sealed_load(run_dir, final, "scope/scope-post.json")
        source = oracle or baseline_scope.get("policy", {})
        policy = ScopePolicy(
            authorized_root=Path(str(source.get("authorized_root", run_dir))),
            writable_paths=tuple(source.get("writable_paths", ())),
            writable_trees=tuple(source.get("writable_trees", ())),
            disposable_trees=tuple(source.get("disposable_trees", ())),
        )
        scope = compare_scope(baseline_scope, post_scope, policy)
        scores.append(
            _receipt(
                "writable_scope",
                final_hash,
                "pass" if not scope["violations"] else "fail",
                scope,
                _evidence(final, "scope/scope-baseline.json", "scope/scope-post.json"),
            )
        )

    if oracle_canary is not None:
        artifact_paths = [run_dir / item["path"] for item in final["artifacts"]]
        leaks = scan_for_leak(oracle_canary, artifact_paths)
        scores.append(
            _receipt(
                "oracle_leak",
                final_hash,
                "invalid" if leaks else "pass",
                {
                    "leaks": [
                        str(Path(path).relative_to(run_dir)) for path in leaks
                    ]
                },
                [],
            )
        )
        required_scorers.add("oracle_leak")

    produced = {score["scorer"]["id"] for score in scores}
    for missing in sorted(required_scorers - produced):
        scores.append(
            _receipt(
                missing,
                final_hash,
                "invalid",
                {"error": "required scorer evidence is missing"},
                [],
            )
        )

    for score in scores:
        _write_content_addressed(output_dir, score)
    overall = (
        "pass"
        if scores and all(item["verdict"] == "pass" for item in scores)
        else "invalid"
        if any(item["verdict"] == "invalid" for item in scores)
        else "fail"
    )
    return {
        "schema": "agent-workflow/score-set/v1",
        "final_receipt_sha256": final_hash,
        "verdict": overall,
        "scores": scores,
    }


def evaluation_policy_for_run(
    run_dir: Path, final_receipt: Mapping[str, Any]
) -> dict[str, Any]:
    """Read evaluation authority from the launch contract, with a sealed legacy fallback."""
    sealed = {
        item.get("path")
        for item in final_receipt.get("artifacts", [])
        if isinstance(item, dict)
    }
    if "launch-contract.json" in sealed:
        contract, _ = read_sealed_json(
            run_dir,
            dict(final_receipt),
            "launch-contract.json",
        )
        if not isinstance(contract, dict):
            raise WorkflowError("sealed launch contract must be a JSON object")
        validate_launch_contract_value(
            contract, artifact=str(run_dir / "launch-contract.json")
        )
        value = contract.get("evaluation_policy", {})
        return value if isinstance(value, dict) else {}
    if "evaluation-runtime.json" in sealed:
        runtime, _ = read_sealed_contract(
            run_dir,
            dict(final_receipt),
            "evaluation-runtime.json",
            "agent-workflow/evaluation-runtime/v1",
        )
        return runtime
    return {}
