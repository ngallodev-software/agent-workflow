from __future__ import annotations

from pathlib import Path

from agent_workflow.contracts import validate_instance
from agent_workflow.eval import scope as scope_module
from agent_workflow.eval.scope import ScopePolicy, collect_scope, compare_scope


def _snapshot(root: Path, receipts: Path, policy: ScopePolicy, phase: str):
    return collect_scope(
        root,
        phase=phase,  # type: ignore[arg-type]
        policy=policy,
        receipt_dir=receipts,
    )


def test_codebase_memory_scope_matrix_distinguishes_source_drift_from_authorized_disposable_state(
    tmp_path: Path, monkeypatch
) -> None:
    cases = (
        {
            "name": "unauthorized",
            "disposable": (),
            "payload": b"{}\n",
            "limit": None,
            "authorized": False,
            "within_limit": True,
            "violates": True,
            "cleanup_policy": "not-authorized",
        },
        {
            "name": "authorized",
            "disposable": (".codebase-memory/",),
            "payload": b"graph",
            "limit": None,
            "authorized": True,
            "within_limit": True,
            "violates": False,
            "cleanup_policy": "host-owned-disposable",
        },
        {
            "name": "oversized",
            "disposable": (".codebase-memory/",),
            "payload": b"12345",
            "limit": 4,
            "authorized": True,
            "within_limit": False,
            "violates": True,
            "cleanup_policy": "host-owned-disposable",
        },
    )

    for case in cases:
        root = tmp_path / case["name"] / "worktree"
        root.mkdir(parents=True)
        receipts = tmp_path / case["name"] / "receipts"
        policy = ScopePolicy(
            authorized_root=root,
            disposable_trees=case["disposable"],
        )
        baseline = _snapshot(root, receipts, policy, "baseline")
        tooling = root / ".codebase-memory"
        tooling.mkdir()
        (tooling / "artifact.bin").write_bytes(case["payload"])
        if case["limit"] is not None:
            monkeypatch.setattr(scope_module, "CODEBASE_MEMORY_MAX_BYTES", case["limit"])
        else:
            monkeypatch.setattr(scope_module, "CODEBASE_MEMORY_MAX_BYTES", 256 * 1024 * 1024)

        post = _snapshot(root, receipts, policy, "post")
        validate_instance(post, "agent-workflow/scope-snapshot/v1", artifact="scope post")
        comparison = compare_scope(baseline, post, policy)
        record = post["tooling_artifacts"][0]

        assert record["path"] == ".codebase-memory/"
        assert record["authorized_disposable"] is case["authorized"]
        assert record["within_size_limit"] is case["within_limit"]
        assert record["cleanup_policy"] == case["cleanup_policy"]
        assert (".codebase-memory/" in comparison["violations"]) is case["violates"]
        if case["authorized"]:
            assert ".codebase-memory/" in post["excluded"]
