from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agent_workflow.contracts import load_schema
from agent_workflow.errors import WorkflowError
from agent_workflow.receipts import seal_run
from agent_workflow.util import atomic_write_json
from agent_workflow.workflow import (
    WORKFLOW_EVENT_SCHEMA,
    WORKFLOW_NODE_BINDING_SCHEMA,
    WORKFLOW_NODE_RESULT_SCHEMA,
    WORKFLOW_RUN_SCHEMA,
    WORKFLOW_SNAPSHOT_SCHEMA,
    WORKFLOW_STATUS_SCHEMA,
    append_workflow_event,
    build_workflow_run,
    initial_status,
    normalize_snapshot,
    record_workflow_binding,
    record_workflow_transition,
    reconstruct_workflow_status,
    snapshot_sha256,
    workflow_events_path,
    workflow_lock,
    workflow_run_path,
    workflow_snapshot_path,
    workflow_status_path,
    write_workflow_projection,
)
from agent_workflow.scheduler import SchedulerService, calculate_eligibility, plan_launches
from agent_workflow.config import defaults
from agent_workflow.workflow_service import WorkflowService
from run_fixtures import write_run_contracts


class WorkflowContractTests(unittest.TestCase):
    def test_workflow_schemas_are_discoverable(self) -> None:
        for schema_id in (
            WORKFLOW_SNAPSHOT_SCHEMA,
            WORKFLOW_NODE_BINDING_SCHEMA,
            WORKFLOW_NODE_RESULT_SCHEMA,
            WORKFLOW_EVENT_SCHEMA,
            WORKFLOW_STATUS_SCHEMA,
            WORKFLOW_RUN_SCHEMA,
        ):
            self.assertEqual(load_schema(schema_id)["$id"], schema_id)


class WorkflowServiceErrorMappingTests(unittest.TestCase):
    def test_start_wraps_filesystem_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps(self._snapshot_data()), encoding="utf-8")
            service = WorkflowService(
                scheduler=SchedulerService(
                    settings=defaults(root / "config.toml"),
                    run_dir=root / "run",
                    workdir=root,
                    launch_fn=lambda *_: {"run_id": "a"},
                )
            )
            with patch("agent_workflow.workflow_service.atomic_write_json", side_effect=OSError("boom")):
                with self.assertRaisesRegex(WorkflowError, "workflow start failed"):
                    service.start(snapshot)

    def test_resume_wraps_filesystem_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = root / "snapshot.json"
            snapshot.write_text(json.dumps(self._snapshot_data()), encoding="utf-8")
            run_dir = root / "run"
            run_dir.mkdir()
            (run_dir / "workflow-run.json").write_text("{}", encoding="utf-8")
            stored_snapshot = run_dir / "workflow-snapshot.json"
            stored_snapshot.write_text(
                snapshot.read_text(encoding="utf-8"), encoding="utf-8"
            )
            stored_snapshot.chmod(0o444)
            settings = replace(
                defaults(root / "config.toml"), state_root=root / "state"
            )

            def launch(_node, run_id):
                write_run_contracts(
                    settings.state_root / "runs" / run_id, session_id=run_id
                )
                return {"run_id": run_id}

            service = WorkflowService(
                scheduler=SchedulerService(
                    settings=settings,
                    run_dir=run_dir,
                    workdir=root,
                    launch_fn=launch,
                )
            )
            with patch("agent_workflow.workflow.atomic_write_json", side_effect=OSError("boom")):
                with self.assertRaisesRegex(WorkflowError, "workflow resume failed"):
                    service.resume(snapshot)

    @staticmethod
    def _snapshot_data() -> dict[str, object]:
        return {
            "schema": WORKFLOW_SNAPSHOT_SCHEMA,
            "workflow_id": "wf-service",
            "pack_id": "pack",
            "pack_manifest_sha256": "a" * 64,
            "nodes": [
                {
                    "node_id": "A",
                    "session_id": "a",
                    "prompt_path": "a.md",
                    "dependencies": [],
                }
            ],
        }


class SchedulerServiceTests(unittest.TestCase):
    def _snapshot(self) -> dict[str, object]:
        return {
            "schema": WORKFLOW_SNAPSHOT_SCHEMA,
            "workflow_id": "wf-scheduler",
            "pack_id": "pack",
            "pack_manifest_sha256": "a" * 64,
            "nodes": [
                {"node_id": "A", "session_id": "a", "prompt_path": "a.md", "dependencies": []},
                {"node_id": "B", "session_id": "b", "prompt_path": "b.md", "dependencies": []},
                {"node_id": "C", "session_id": "c", "prompt_path": "c.md", "dependencies": ["A"]},
            ],
        }

    def test_eligibility_is_bounded_and_failed_prerequisite_blocks_dependent(self):
        snapshot = normalize_snapshot(self._snapshot())
        status = initial_status(snapshot)
        self.assertEqual(calculate_eligibility(snapshot, status), ["A", "B"])
        self.assertEqual(plan_launches(snapshot, status, max_parallelism=1), ["A"])
        status["nodes"][0]["state"] = "failed"
        self.assertEqual(calculate_eligibility(snapshot, status), ["B"])

    def test_running_nodes_consume_parallelism_capacity(self):
        snapshot = normalize_snapshot(self._snapshot())
        status = initial_status(snapshot)
        by_id = {item["node_id"]: item for item in status["nodes"]}
        by_id["A"].update(state="running", run_id="a", attempt=1)
        self.assertEqual(plan_launches(snapshot, status, max_parallelism=1), [])
        self.assertEqual(plan_launches(snapshot, status, max_parallelism=2), ["B"])

    def test_launch_is_idempotent_on_replay_and_parallelism_is_bounded(self):
        snapshot = normalize_snapshot(self._snapshot())
        snapshot["nodes"] = [snapshot["nodes"][0]]
        snapshot = normalize_snapshot(snapshot)
        active = 0
        maximum = 0
        calls: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")

            def launch(node, run_id):
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                calls.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                active -= 1
                return {"run_id": run_id}

            service = SchedulerService(
                settings=settings,
                run_dir=Path(tmp) / "workflow",
                workdir=Path(tmp),
                max_parallelism=1,
                launch_fn=launch,
            )
            first = service.launch_eligible(snapshot)
            second = service.launch_eligible(snapshot)
            self.assertEqual(len(first["plans"]), 1)
            self.assertEqual(second["plans"], [])
            self.assertEqual(calls, ["a"])
            self.assertEqual(maximum, 1)

    def test_recoverable_node_can_be_retried_and_replayed(self):
        snapshot = normalize_snapshot({**self._snapshot(), "nodes": [self._snapshot()["nodes"][0]]})
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "workflow"
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")
            digest = snapshot_sha256(snapshot)
            record_workflow_binding(
                run_dir, workflow_id="wf-scheduler", node_id="A", run_id="a",
                attempt=1, actor="test", reason="bound", snapshot_sha256=digest,
            )
            record_workflow_transition(
                run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                reason="running", snapshot_sha256=digest,
                previous_state="eligible", next_state="running",
            )
            record_workflow_transition(
                run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                reason="manual recovery required", snapshot_sha256=digest,
                previous_state="running", next_state="recoverable",
            )

            def launch(node, run_id):
                calls.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = SchedulerService(
                settings=settings, run_dir=run_dir, workdir=root, launch_fn=launch,
            )
            result = service.retry(snapshot, "A")
            self.assertEqual(result["plan"]["attempt"], 2)
            self.assertEqual(result["plan"]["retry_of_run_id"], "a")
            self.assertEqual(calls, ["a-retry-2"])
            replayed = service.status(snapshot)
            self.assertEqual(replayed["nodes"][0]["state"], "running")
            self.assertEqual(replayed["nodes"][0]["attempt"], 2)

    def test_failed_launch_can_be_retried_with_lineage(self):
        snapshot = normalize_snapshot(self._snapshot())
        calls: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")

            def launch(node, run_id):
                calls.append(run_id)
                if len(calls) == 1:
                    raise RuntimeError("synthetic launch failure")
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = SchedulerService(
                settings=settings,
                run_dir=root / "workflow",
                workdir=root,
                launch_fn=launch,
            )
            with self.assertRaises(RuntimeError):
                service.launch_eligible(snapshot)
            result = service.retry(snapshot, "A")
            self.assertEqual(result["plan"]["attempt"], 2)
            self.assertEqual(result["plan"]["retry_of_run_id"], "a")
            self.assertEqual(calls, ["a", "a-retry-2"])

    def test_two_services_serialize_binding_and_external_launch(self):
        snapshot = normalize_snapshot(self._snapshot())
        calls: list[str] = []
        calls_lock = threading.Lock()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "workflow"
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")

            def launch(node, run_id):
                with calls_lock:
                    calls.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                time.sleep(0.05)
                return {"run_id": run_id}

            services = [
                SchedulerService(settings=settings, run_dir=run_dir,
                                 workdir=root, launch_fn=launch)
                for i in range(2)
            ]
            threads = [threading.Thread(target=service.launch_eligible, args=(snapshot,)) for service in services]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(calls, ["a"])
            self.assertEqual(services[0].status(snapshot)["nodes"][0]["state"], "running")

    def test_running_event_cannot_circularly_prove_deleted_child_exists(self):
        snapshot = normalize_snapshot({**self._snapshot(), "nodes": [self._snapshot()["nodes"][0]]})
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "workflow"
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")
            digest = snapshot_sha256(snapshot)
            record_workflow_binding(
                run_dir, workflow_id="wf-scheduler", node_id="A", run_id="a",
                attempt=1, actor="test", reason="bound", snapshot_sha256=digest,
            )
            record_workflow_transition(
                run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                reason="authoritative child once existed", snapshot_sha256=digest,
                previous_state="eligible", next_state="running",
                details={"child_run_id": "a"},
            )
            service = SchedulerService(
                settings=settings, run_dir=run_dir, workdir=root,
                launch_fn=lambda node, run_id: calls.append(run_id),
            )
            service.launch_eligible(snapshot)
            self.assertEqual(service.status(snapshot)["nodes"][0]["state"], "recoverable")
            self.assertEqual(calls, [])

    def test_resume_reconciles_sealed_child_and_launches_dependent(self):
        snapshot = normalize_snapshot(
            {**self._snapshot(), "nodes": [self._snapshot()["nodes"][0], self._snapshot()["nodes"][2]]}
        )
        launched: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")
            child = settings.state_root / "runs" / "a"
            write_run_contracts(child, session_id="a")
            completion = json.loads((child / "completion.json").read_text(encoding="utf-8"))
            completion.update(result="completed", head_revision="abc123", unresolved=[])
            atomic_write_json(child / "completion.json", completion)
            final_status = json.loads((child / "final-status.json").read_text(encoding="utf-8"))
            final_status.update(status="completed")
            atomic_write_json(child / "final-status.json", final_status)
            seal_run(child, session_id="a")

            run_dir = root / "workflow"
            digest = snapshot_sha256(snapshot)
            record_workflow_binding(
                run_dir, workflow_id="wf-scheduler", node_id="A", run_id="a",
                attempt=1, actor="test", reason="bound", snapshot_sha256=digest,
            )
            record_workflow_transition(
                run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                reason="running", snapshot_sha256=digest,
                previous_state="eligible", next_state="running",
                details={"child_run_id": "a"},
            )

            def launch(node, run_id):
                launched.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = SchedulerService(
                settings=settings, run_dir=run_dir, workdir=root, launch_fn=launch,
            )
            service.launch_eligible(snapshot)
            status = {item["node_id"]: item for item in service.status(snapshot)["nodes"]}
            self.assertEqual(status["A"]["state"], "completed")
            self.assertEqual(status["C"]["state"], "running")
            self.assertEqual(launched, ["c"])

    def test_mapping_only_launch_result_is_not_authoritative(self):
        snapshot = normalize_snapshot(
            {**self._snapshot(), "nodes": [self._snapshot()["nodes"][0]]}
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")
            service = SchedulerService(
                settings=settings,
                run_dir=root / "workflow",
                workdir=root,
                launch_fn=lambda node, run_id: {"run_id": run_id},
            )
            with self.assertRaisesRegex(WorkflowError, "no authoritative child run"):
                service.launch_eligible(snapshot)
            self.assertEqual(service.status(snapshot)["nodes"][0]["state"], "recoverable")

    def test_retry_reopens_dependency_failed_descendants(self):
        snapshot = normalize_snapshot(
            {**self._snapshot(), "nodes": [self._snapshot()["nodes"][0], self._snapshot()["nodes"][2]]}
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")
            run_dir = root / "workflow"
            digest = snapshot_sha256(snapshot)
            record_workflow_binding(
                run_dir, workflow_id="wf-scheduler", node_id="A", run_id="a",
                attempt=1, actor="test", reason="bound", snapshot_sha256=digest,
            )
            record_workflow_transition(
                run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                reason="running", snapshot_sha256=digest,
                previous_state="eligible", next_state="running",
            )
            record_workflow_transition(
                run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                reason="failed", snapshot_sha256=digest,
                previous_state="running", next_state="failed",
            )
            launched: list[str] = []

            def launch(node, run_id):
                launched.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = SchedulerService(
                settings=settings, run_dir=run_dir, workdir=root, launch_fn=launch,
            )
            service.launch_eligible(snapshot)
            by_id = {item["node_id"]: item for item in service.status(snapshot)["nodes"]}
            self.assertEqual(by_id["C"]["state"], "failed")

            service.retry(snapshot, "A")
            service.launch_eligible(snapshot)
            by_id = {item["node_id"]: item for item in service.status(snapshot)["nodes"]}
            self.assertEqual(by_id["A"]["state"], "running")
            self.assertEqual(by_id["C"]["state"], "blocked")

            retry_run = settings.state_root / "runs" / "a-retry-2"
            completion = json.loads((retry_run / "completion.json").read_text(encoding="utf-8"))
            completion.update(result="completed", head_revision="abc123", unresolved=[])
            atomic_write_json(retry_run / "completion.json", completion)
            final_status = json.loads((retry_run / "final-status.json").read_text(encoding="utf-8"))
            final_status.update(status="completed")
            atomic_write_json(retry_run / "final-status.json", final_status)
            seal_run(retry_run, session_id="a-retry-2")

            service.launch_eligible(snapshot)
            by_id = {item["node_id"]: item for item in service.status(snapshot)["nodes"]}
            self.assertEqual(by_id["A"]["state"], "completed")
            self.assertEqual(by_id["C"]["state"], "running")
            self.assertEqual(launched, ["a-retry-2", "c"])

    def test_restart_windows_reuse_binding_and_fail_closed_running_without_child(self):
        snapshot = normalize_snapshot(self._snapshot())
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "workflow"
            settings = replace(defaults(Path(tmp) / "config.toml"), state_root=Path(tmp) / "state")
            digest = snapshot_sha256(snapshot)
            record_workflow_binding(run_dir, workflow_id="wf-scheduler", node_id="A", run_id="a",
                                    attempt=1, actor="scheduler", reason="crash after binding", snapshot_sha256=digest)

            def launch(node, run_id):
                calls.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = SchedulerService(settings=settings, run_dir=run_dir, workdir=Path(tmp), launch_fn=launch)
            service.launch_eligible(snapshot)
            self.assertEqual(calls, ["a"])
            record_workflow_transition(run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                                       reason="inject crash after running", snapshot_sha256=digest,
                                       previous_state="running", next_state="recoverable")
            self.assertEqual(service.status(snapshot)["nodes"][0]["state"], "recoverable")

            shutil.rmtree(settings.state_root / "runs" / "a")
            orphan_dir = Path(tmp) / "orphan-workflow"
            orphan_snapshot = normalize_snapshot({**snapshot, "nodes": [snapshot["nodes"][0]]})
            orphan_digest = snapshot_sha256(orphan_snapshot)
            record_workflow_binding(orphan_dir, workflow_id="wf-scheduler", node_id="A", run_id="a",
                                    attempt=1, actor="test", reason="seed binding", snapshot_sha256=orphan_digest)
            record_workflow_transition(orphan_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                                       reason="seed running crash window", snapshot_sha256=orphan_digest,
                                       previous_state="eligible", next_state="running")
            orphan_service = SchedulerService(settings=settings, run_dir=orphan_dir, workdir=Path(tmp), launch_fn=launch)
            orphan_service.launch_eligible(orphan_snapshot)
            self.assertEqual(orphan_service.status(orphan_snapshot)["nodes"][0]["state"], "recoverable")
            self.assertEqual(calls, ["a"])

    def test_completed_prerequisite_is_journaled_before_dependent_launch_and_provenance_is_forwarded(self):
        snapshot = normalize_snapshot(self._snapshot())
        snapshot["nodes"] = [snapshot["nodes"][0], snapshot["nodes"][2]]
        snapshot = normalize_snapshot(snapshot)
        run_dir = None
        seen: list[dict[str, object]] = []
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "workflow"
            digest = snapshot_sha256(snapshot)
            record_workflow_binding(run_dir, workflow_id="wf-scheduler", node_id="A", run_id="a", attempt=1,
                                    actor="test", reason="A bound", snapshot_sha256=digest)
            record_workflow_transition(run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                                       reason="A running", snapshot_sha256=digest, previous_state="eligible", next_state="running")
            record_workflow_transition(run_dir, workflow_id="wf-scheduler", node_id="A", actor="test",
                                       reason="A complete", snapshot_sha256=digest, previous_state="running", next_state="completed")

            settings = replace(defaults(Path(tmp) / "config.toml"), state_root=Path(tmp) / "state")

            def launch(node, run_id):
                seen.append(dict(node))
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = SchedulerService(settings=settings, run_dir=run_dir,
                                       workdir=Path(tmp), launch_fn=launch)
            service.launch_eligible(snapshot)
            self.assertEqual(seen[0]["node_id"], "C")
            self.assertEqual(seen[0]["pack_id"], "pack")
            self.assertIsNone(seen[0]["retry_of_run_id"])
            events = [json.loads(line) for line in workflow_events_path(run_dir).read_text().splitlines()]
            self.assertTrue(any(event.get("previous_state") == "blocked" and event.get("next_state") == "eligible" for event in events))


class WorkflowReplayTests(unittest.TestCase):
    @staticmethod
    def _snapshot() -> dict[str, object]:
        return {
            "schema": WORKFLOW_SNAPSHOT_SCHEMA,
            "workflow_id": "wf-contract",
            "pack_id": "workflow-foundations-next",
            "pack_manifest_sha256": "0" * 64,
            "nodes": [
                {
                    "node_id": "A",
                    "ticket_id": "WF-00",
                    "session_id": "wf-00",
                    "tier": "B",
                    "prompt_path": "phase-0/tickets/WF-00-contract-and-state.md",
                    "dependencies": [],
                },
                {
                    "node_id": "B",
                    "ticket_id": "WF-01",
                    "session_id": "wf-01",
                    "tier": "A",
                    "prompt_path": "phase-0/tickets/WF-01-scheduler-service.md",
                    "dependencies": ["A"],
                },
            ],
        }

    @staticmethod
    def _write_events(path: Path, events: list[dict[str, object]]) -> None:
        path.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )

    def test_snapshot_rejects_unknown_and_cyclic_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unknown = self._snapshot()
            unknown["nodes"] = [
                unknown["nodes"][0],
                {
                    "node_id": "C",
                    "session_id": "wf-02",
                    "prompt_path": "phase-0/tickets/WF-02-restart-and-cli.md",
                    "dependencies": ["missing"],
                },
            ]
            with self.assertRaisesRegex(WorkflowError, "unknown dependency"):
                normalize_snapshot(unknown)

            cyclic = self._snapshot()
            cyclic["nodes"] = [
                {
                    "node_id": "A",
                    "session_id": "wf-00",
                    "prompt_path": "phase-0/tickets/WF-00-contract-and-state.md",
                    "dependencies": ["B"],
                },
                {
                    "node_id": "B",
                    "session_id": "wf-01",
                    "prompt_path": "phase-0/tickets/WF-01-scheduler-service.md",
                    "dependencies": ["A"],
                },
            ]
            with self.assertRaisesRegex(WorkflowError, "dependency cycle"):
                normalize_snapshot(cyclic)

    def test_snapshot_rejects_duplicate_dependencies_and_session_ids(self) -> None:
        duplicate_dependency = self._snapshot()
        duplicate_dependency["nodes"][1]["dependencies"] = ["A", "A"]
        with self.assertRaisesRegex(WorkflowError, "duplicate dependency"):
            normalize_snapshot(duplicate_dependency)

        duplicate_session = self._snapshot()
        duplicate_session["nodes"][1]["session_id"] = "wf-00"
        with self.assertRaisesRegex(WorkflowError, "duplicate workflow session ID"):
            normalize_snapshot(duplicate_session)

    def test_event_journal_rejects_symlink_and_corrupt_existing_content(self) -> None:
        snapshot = normalize_snapshot(self._snapshot())
        digest = snapshot_sha256(snapshot)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "symlink"
            run_dir.mkdir()
            target = Path(tmp) / "target.jsonl"
            target.touch()
            os.symlink(target, workflow_events_path(run_dir))
            with self.assertRaises(WorkflowError):
                record_workflow_binding(
                    run_dir, workflow_id="wf-contract", node_id="A", run_id="wf-00",
                    attempt=1, actor="test", reason="bound", snapshot_sha256=digest,
                )

            lock_dir = Path(tmp) / "lock-symlink"
            lock_dir.mkdir()
            os.symlink(target, lock_dir / "workflow.lock")
            with self.assertRaises(WorkflowError):
                with workflow_lock(lock_dir):
                    self.fail("symlink workflow lock should not be acquired")

            corrupt_dir = Path(tmp) / "corrupt"
            corrupt_dir.mkdir()
            workflow_events_path(corrupt_dir).write_text("{}\n", encoding="utf-8")
            with self.assertRaises(WorkflowError):
                record_workflow_binding(
                    corrupt_dir, workflow_id="wf-contract", node_id="A", run_id="wf-00",
                    attempt=1, actor="test", reason="bound", snapshot_sha256=digest,
                )
            self.assertEqual(workflow_events_path(corrupt_dir).read_text(encoding="utf-8"), "{}\n")

    def test_replay_reconstructs_status_from_snapshot_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            snapshot = normalize_snapshot(self._snapshot())
            snapshot_path = workflow_snapshot_path(run_dir)
            events_path = workflow_events_path(run_dir)
            status_path = workflow_status_path(run_dir)
            run_path = workflow_run_path(run_dir)
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            digest = snapshot_sha256(snapshot)

            record_workflow_binding(
                run_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="A",
                run_id="wf-00-run",
                attempt=1,
                actor="scheduler",
                reason="launch A",
                snapshot_sha256=digest,
            )
            record_workflow_transition(
                run_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="A",
                actor="scheduler",
                reason="A running",
                snapshot_sha256=digest,
                previous_state="eligible",
                next_state="running",
            )
            record_workflow_transition(
                run_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="A",
                actor="scheduler",
                reason="A complete",
                snapshot_sha256=digest,
                previous_state="running",
                next_state="completed",
            )
            record_workflow_transition(
                run_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="B",
                actor="scheduler",
                reason="dependency cleared",
                snapshot_sha256=digest,
                previous_state="blocked",
                next_state="eligible",
            )
            record_workflow_binding(
                run_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="B",
                run_id="wf-01-run",
                attempt=1,
                actor="scheduler",
                reason="launch B",
                snapshot_sha256=digest,
            )
            record_workflow_transition(
                run_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="B",
                actor="scheduler",
                reason="B running",
                snapshot_sha256=digest,
                previous_state="eligible",
                next_state="running",
            )
            record_workflow_transition(
                run_dir,
                workflow_id=snapshot["workflow_id"],
                node_id="B",
                actor="scheduler",
                reason="B failed",
                snapshot_sha256=digest,
                previous_state="running",
                next_state="failed",
            )

            status = reconstruct_workflow_status(snapshot, events_path)
            self.assertEqual(status["workflow_state"], "failed")
            self.assertEqual(status["event_count"], 7)
            self.assertEqual([item["state"] for item in status["nodes"]], ["completed", "failed"])
            self.assertEqual(status["nodes"][0]["run_id"], "wf-00-run")
            self.assertEqual(status["nodes"][1]["run_id"], "wf-01-run")
            self.assertEqual(status["nodes"][1]["terminal_reason"], "B failed")
            run = build_workflow_run(
                snapshot=snapshot,
                snapshot_path=snapshot_path,
                events_path=events_path,
                status_path=status_path,
            )
            self.assertEqual(run["status"]["workflow_state"], "failed")
            self.assertEqual(run["snapshot_sha256"], digest)

            write_workflow_projection(
                snapshot=snapshot,
                snapshot_path=snapshot_path,
                events_path=events_path,
                status_path=status_path,
                run_path=run_path,
            )
            self.assertTrue(status_path.is_file())
            self.assertTrue(run_path.is_file())

    def test_replay_allows_failed_node_retry_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            snapshot = normalize_snapshot(
                {
                    "schema": WORKFLOW_SNAPSHOT_SCHEMA,
                    "workflow_id": "wf-retry",
                    "pack_id": "workflow-foundations-next",
                    "pack_manifest_sha256": "2" * 64,
                    "nodes": [
                        {
                            "node_id": "A",
                            "session_id": "wf-00",
                            "prompt_path": "phase-0/tickets/WF-00-contract-and-state.md",
                            "dependencies": [],
                        }
                    ],
                }
            )
            digest = snapshot_sha256(snapshot)
            events_path = workflow_events_path(run_dir)
            self._write_events(
                events_path,
                [
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 1,
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "workflow_id": "wf-retry",
                        "kind": "node-bound",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "launch A",
                        "snapshot_sha256": digest,
                        "previous_state": None,
                        "next_state": None,
                        "binding": {
                            "run_id": "wf-00-run",
                            "attempt": 1,
                            "retry_of_run_id": None,
                            "bound_at": "2026-01-01T00:00:00+00:00",
                            "current": True,
                        },
                        "details": None,
                    },
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 2,
                        "timestamp": "2026-01-01T00:01:00+00:00",
                        "workflow_id": "wf-retry",
                        "kind": "node-transition",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "A running",
                        "snapshot_sha256": digest,
                        "previous_state": "eligible",
                        "next_state": "running",
                        "binding": None,
                        "details": None,
                    },
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 3,
                        "timestamp": "2026-01-01T00:02:00+00:00",
                        "workflow_id": "wf-retry",
                        "kind": "node-transition",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "A failed",
                        "snapshot_sha256": digest,
                        "previous_state": "running",
                        "next_state": "failed",
                        "binding": None,
                        "details": None,
                    },
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 4,
                        "timestamp": "2026-01-01T00:03:00+00:00",
                        "workflow_id": "wf-retry",
                        "kind": "node-bound",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "retry A",
                        "snapshot_sha256": digest,
                        "previous_state": None,
                        "next_state": None,
                        "binding": {
                            "run_id": "wf-00-run-retry",
                            "attempt": 2,
                            "retry_of_run_id": "wf-00-run",
                            "bound_at": "2026-01-01T00:03:00+00:00",
                            "current": True,
                        },
                        "details": None,
                    },
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 5,
                        "timestamp": "2026-01-01T00:04:00+00:00",
                        "workflow_id": "wf-retry",
                        "kind": "node-transition",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "retry released",
                        "snapshot_sha256": digest,
                        "previous_state": "failed",
                        "next_state": "eligible",
                        "binding": None,
                        "details": None,
                    },
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 6,
                        "timestamp": "2026-01-01T00:05:00+00:00",
                        "workflow_id": "wf-retry",
                        "kind": "node-transition",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "retry running",
                        "snapshot_sha256": digest,
                        "previous_state": "eligible",
                        "next_state": "running",
                        "binding": None,
                        "details": None,
                    },
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 7,
                        "timestamp": "2026-01-01T00:06:00+00:00",
                        "workflow_id": "wf-retry",
                        "kind": "node-transition",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "retry complete",
                        "snapshot_sha256": digest,
                        "previous_state": "running",
                        "next_state": "completed",
                        "binding": None,
                        "details": None,
                    },
                ],
            )
            status = reconstruct_workflow_status(snapshot, events_path)
            self.assertEqual(status["workflow_state"], "completed")
            self.assertEqual(status["nodes"][0]["state"], "completed")
            self.assertEqual(status["nodes"][0]["run_id"], "wf-00-run-retry")
            self.assertEqual(status["nodes"][0]["attempt"], 2)
            self.assertEqual(status["nodes"][0]["retry_of_run_id"], "wf-00-run")
            self.assertEqual(status["nodes"][0]["terminal_reason"], "retry complete")

    def test_replay_reports_completed_for_terminal_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            snapshot = normalize_snapshot(
                {
                    "schema": WORKFLOW_SNAPSHOT_SCHEMA,
                    "workflow_id": "wf-done",
                    "pack_id": "workflow-foundations-next",
                    "pack_manifest_sha256": "1" * 64,
                    "nodes": [
                        {
                            "node_id": "A",
                            "session_id": "wf-00",
                            "prompt_path": "phase-0/tickets/WF-00-contract-and-state.md",
                            "dependencies": [],
                        }
                    ],
                }
            )
            digest = snapshot_sha256(snapshot)
            events_path = workflow_events_path(run_dir)
            record_workflow_binding(
                run_dir,
                workflow_id="wf-done",
                node_id="A",
                run_id="wf-00-run",
                attempt=1,
                actor="scheduler",
                reason="launch A",
                snapshot_sha256=digest,
            )
            record_workflow_transition(
                run_dir,
                workflow_id="wf-done",
                node_id="A",
                actor="scheduler",
                reason="running",
                snapshot_sha256=digest,
                previous_state="eligible",
                next_state="running",
            )
            record_workflow_transition(
                run_dir,
                workflow_id="wf-done",
                node_id="A",
                actor="scheduler",
                reason="finished",
                snapshot_sha256=digest,
                previous_state="running",
                next_state="completed",
            )
            status = reconstruct_workflow_status(snapshot, events_path)
            self.assertEqual(status["workflow_state"], "completed")
            self.assertEqual(status["nodes"][0]["state"], "completed")

    def test_replay_rejects_unbound_execution_and_dependency_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            snapshot = normalize_snapshot(self._snapshot())
            digest = snapshot_sha256(snapshot)
            events_path = workflow_events_path(run_dir)

            self._write_events(
                events_path,
                [
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 1,
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "workflow_id": "wf-contract",
                        "kind": "node-transition",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "unbound run",
                        "snapshot_sha256": digest,
                        "previous_state": "eligible",
                        "next_state": "running",
                        "binding": None,
                        "details": None,
                    }
                ],
            )
            with self.assertRaisesRegex(WorkflowError, "without a current binding"):
                reconstruct_workflow_status(snapshot, events_path)

            self._write_events(
                events_path,
                [
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 1,
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "workflow_id": "wf-contract",
                        "kind": "node-transition",
                        "node_id": "B",
                        "actor": "scheduler",
                        "reason": "too early",
                        "snapshot_sha256": digest,
                        "previous_state": "blocked",
                        "next_state": "eligible",
                        "binding": None,
                        "details": None,
                    }
                ],
            )
            with self.assertRaisesRegex(WorkflowError, "dependencies complete"):
                reconstruct_workflow_status(snapshot, events_path)

    def test_replay_rejects_invalid_binding_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            snapshot = normalize_snapshot(self._snapshot())
            digest = snapshot_sha256(snapshot)
            events_path = workflow_events_path(run_dir)

            cases = [
                (
                    "must be current",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "not current",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 1,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": False,
                            },
                            "details": None,
                        }
                    ],
                ),
                (
                    "first binding must use attempt 1",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "bad attempt",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 2,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        }
                    ],
                ),
                (
                    "first binding cannot have retry lineage",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "bad retry lineage",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 1,
                                "retry_of_run_id": "wf-previous-run",
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        }
                    ],
                ),
                (
                    "retry attempt must be the next attempt",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "launch A",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 1,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 2,
                            "timestamp": "2026-01-01T00:01:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A running",
                            "snapshot_sha256": digest,
                            "previous_state": "eligible",
                            "next_state": "running",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 3,
                            "timestamp": "2026-01-01T00:02:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A failed",
                            "snapshot_sha256": digest,
                            "previous_state": "running",
                            "next_state": "failed",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 4,
                            "timestamp": "2026-01-01T00:03:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "skip attempt",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run-retry",
                                "attempt": 3,
                                "retry_of_run_id": "wf-00-run",
                                "bound_at": "2026-01-01T00:03:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                    ],
                ),
                (
                    "retry must reference the current run",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "launch A",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 1,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 2,
                            "timestamp": "2026-01-01T00:01:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A running",
                            "snapshot_sha256": digest,
                            "previous_state": "eligible",
                            "next_state": "running",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 3,
                            "timestamp": "2026-01-01T00:02:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A failed",
                            "snapshot_sha256": digest,
                            "previous_state": "running",
                            "next_state": "failed",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 4,
                            "timestamp": "2026-01-01T00:03:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "wrong parent",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run-retry",
                                "attempt": 2,
                                "retry_of_run_id": "wf-wrong-parent",
                                "bound_at": "2026-01-01T00:03:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                    ],
                ),
                (
                    "run ID reused",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "launch A",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 1,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 2,
                            "timestamp": "2026-01-01T00:01:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A running",
                            "snapshot_sha256": digest,
                            "previous_state": "eligible",
                            "next_state": "running",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 3,
                            "timestamp": "2026-01-01T00:02:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A failed",
                            "snapshot_sha256": digest,
                            "previous_state": "running",
                            "next_state": "failed",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 4,
                            "timestamp": "2026-01-01T00:03:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "reused",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 2,
                                "retry_of_run_id": "wf-00-run",
                                "bound_at": "2026-01-01T00:03:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                    ],
                ),
                (
                    "cannot be bound while blocked",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "B",
                            "actor": "scheduler",
                            "reason": "too early",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-01-run",
                                "attempt": 1,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        }
                    ],
                ),
                (
                    "cannot be bound while running",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "launch A",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 1,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 2,
                            "timestamp": "2026-01-01T00:01:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A running",
                            "snapshot_sha256": digest,
                            "previous_state": "eligible",
                            "next_state": "running",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 3,
                            "timestamp": "2026-01-01T00:02:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "double bind",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run-2",
                                "attempt": 2,
                                "retry_of_run_id": "wf-00-run",
                                "bound_at": "2026-01-01T00:02:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                    ],
                ),
                (
                    "cannot be bound while completed",
                    [
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 1,
                            "timestamp": "2026-01-01T00:00:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "launch A",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run",
                                "attempt": 1,
                                "retry_of_run_id": None,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 2,
                            "timestamp": "2026-01-01T00:01:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A running",
                            "snapshot_sha256": digest,
                            "previous_state": "eligible",
                            "next_state": "running",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 3,
                            "timestamp": "2026-01-01T00:02:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-transition",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "A complete",
                            "snapshot_sha256": digest,
                            "previous_state": "running",
                            "next_state": "completed",
                            "binding": None,
                            "details": None,
                        },
                        {
                            "schema": WORKFLOW_EVENT_SCHEMA,
                            "sequence": 4,
                            "timestamp": "2026-01-01T00:03:00+00:00",
                            "workflow_id": "wf-contract",
                            "kind": "node-bound",
                            "node_id": "A",
                            "actor": "scheduler",
                            "reason": "late bind",
                            "snapshot_sha256": digest,
                            "previous_state": None,
                            "next_state": None,
                            "binding": {
                                "run_id": "wf-00-run-2",
                                "attempt": 2,
                                "retry_of_run_id": "wf-00-run",
                                "bound_at": "2026-01-01T00:03:00+00:00",
                                "current": True,
                            },
                            "details": None,
                        },
                    ],
                ),
            ]
            for expected, events in cases:
                with self.subTest(expected=expected):
                    self._write_events(events_path, events)
                    with self.assertRaisesRegex(WorkflowError, expected):
                        reconstruct_workflow_status(snapshot, events_path)

    def test_replay_rejects_corruption_and_invalid_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            snapshot = normalize_snapshot(self._snapshot())
            digest = snapshot_sha256(snapshot)
            events_path = workflow_events_path(run_dir)
            record_workflow_transition(
                run_dir,
                workflow_id="wf-contract",
                node_id="A",
                actor="scheduler",
                reason="bad transition",
                snapshot_sha256=digest,
                previous_state="blocked",
                next_state="completed",
            )
            with self.assertRaisesRegex(WorkflowError, "invalid workflow transition"):
                reconstruct_workflow_status(snapshot, events_path)

            events_path.write_text("not json\n", encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "invalid workflow event JSON"):
                reconstruct_workflow_status(snapshot, events_path)

            events_path.write_text(
                json.dumps(
                    {
                        "schema": WORKFLOW_EVENT_SCHEMA,
                        "sequence": 2,
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "workflow_id": "wf-contract",
                        "kind": "node-transition",
                        "node_id": "A",
                        "actor": "scheduler",
                        "reason": "bad sequence",
                        "snapshot_sha256": digest,
                        "previous_state": "eligible",
                        "next_state": "running",
                        "binding": None,
                        "details": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(WorkflowError, "sequence mismatch"):
                reconstruct_workflow_status(snapshot, events_path)


class WorkflowServiceTests(unittest.TestCase):
    def _snapshot(self, *, terminal: bool = False) -> dict[str, object]:
        nodes = [
            {"node_id": "A", "session_id": "wf-a", "prompt_path": "a.md", "dependencies": []},
            {"node_id": "B", "session_id": "wf-b", "prompt_path": "b.md", "dependencies": ["A"]},
        ]
        snapshot = {
            "schema": WORKFLOW_SNAPSHOT_SCHEMA,
            "workflow_id": "wf-cli",
            "pack_id": "pack",
            "pack_manifest_sha256": "1" * 64,
            "nodes": [nodes[0]] if terminal else nodes,
        }
        return normalize_snapshot(snapshot)

    def test_validate_start_status_and_resume_share_result_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path = root / "snapshot.json"
            snapshot = self._snapshot()
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            run_dir = root / "workflow"
            launched: list[str] = []

            settings = replace(defaults(root / "config.toml"), state_root=root / "state")

            def launch(node, run_id):
                launched.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = WorkflowService(
                scheduler=SchedulerService(
                    settings=settings,
                    run_dir=run_dir,
                    workdir=root,
                    launch_fn=launch,
                )
            )

            validate = service.validate(snapshot_path)
            self.assertEqual(validate["schema"], WORKFLOW_NODE_RESULT_SCHEMA)
            self.assertEqual(validate["action"], "validate")
            self.assertEqual(validate["result"]["node_count"], 2)

            start = service.start(snapshot_path)
            self.assertEqual(start["started"], True)
            self.assertEqual(start["scheduled"], ["A"])
            self.assertEqual(launched, ["wf-a"])
            self.assertTrue((run_dir / "workflow-run.json").is_file())
            projected_status = json.loads(
                workflow_status_path(run_dir).read_text(encoding="utf-8")
            )
            projected_run = json.loads(
                workflow_run_path(run_dir).read_text(encoding="utf-8")
            )
            self.assertEqual(projected_status["workflow_state"], "running")
            self.assertEqual(projected_run["status"], projected_status)

            status = service.status(snapshot_path)
            self.assertEqual(status["action"], "status")
            self.assertEqual(status["result"]["workflow_state"], "running")

            changed = json.loads(snapshot_path.read_text(encoding="utf-8"))
            changed["pack_manifest_sha256"] = "2" * 64
            snapshot_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowError, "does not match"):
                service.status(snapshot_path)
            with self.assertRaisesRegex(WorkflowError, "does not match"):
                service.resume(snapshot_path)
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            resume = service.resume(snapshot_path)
            self.assertEqual(resume["resumed"], True)
            self.assertEqual(resume["scheduled"], [])

    def test_status_recovers_missing_mutable_projections_from_canonical_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = self._snapshot(terminal=True)
            snapshot_path = root / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")

            def launch(_node, run_id):
                write_run_contracts(
                    settings.state_root / "runs" / run_id, session_id=run_id
                )
                return {"run_id": run_id}

            run_dir = root / "workflow"
            service = WorkflowService(
                scheduler=SchedulerService(
                    settings=settings, run_dir=run_dir, workdir=root, launch_fn=launch
                )
            )
            service.start(snapshot_path)
            workflow_status_path(run_dir).unlink()
            workflow_run_path(run_dir).unlink()

            status = service.status(snapshot_path)

            self.assertEqual(status["result"]["workflow_state"], "running")
            self.assertTrue(workflow_status_path(run_dir).is_file())
            self.assertTrue(workflow_run_path(run_dir).is_file())

    def test_started_snapshot_is_read_only_and_writable_tampering_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = self._snapshot(terminal=True)
            snapshot_path = root / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            settings = replace(defaults(root / "config.toml"), state_root=root / "state")

            def launch(node, run_id):
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = WorkflowService(
                scheduler=SchedulerService(
                    settings=settings, run_dir=root / "workflow", workdir=root, launch_fn=launch,
                )
            )
            service.start(snapshot_path)
            stored = workflow_snapshot_path(root / "workflow")
            self.assertEqual(stored.stat().st_mode & 0o222, 0)
            stored.chmod(0o644)
            with self.assertRaisesRegex(WorkflowError, "read-only"):
                service.status(snapshot_path)

    def test_duplicate_start_invalid_root_and_terminal_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot_path = root / "snapshot.json"
            snapshot = self._snapshot(terminal=True)
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            run_dir = root / "workflow"
            launches: list[str] = []

            settings = replace(defaults(root / "config.toml"), state_root=root / "state")

            def launch(node, run_id):
                launches.append(run_id)
                write_run_contracts(settings.state_root / "runs" / run_id, session_id=run_id)
                return {"run_id": run_id}

            service = WorkflowService(
                scheduler=SchedulerService(
                    settings=settings,
                    run_dir=run_dir,
                    workdir=root,
                    launch_fn=launch,
                )
            )
            service.start(snapshot_path)
            digest = snapshot_sha256(snapshot)
            record_workflow_transition(
                run_dir,
                workflow_id="wf-cli",
                node_id="A",
                actor="test",
                reason="terminal complete",
                snapshot_sha256=digest,
                previous_state="running",
                next_state="completed",
            )
            with self.assertRaisesRegex(WorkflowError, "already started"):
                service.start(snapshot_path)
            self.assertEqual(service.resume(snapshot_path)["scheduled"], [])
            self.assertEqual(launches, ["wf-a"])
            missing = WorkflowService(
                scheduler=SchedulerService(
                    settings=defaults(root / "config.toml"),
                    run_dir=root / "missing",
                    workdir=root,
                )
            )
            with self.assertRaisesRegex(WorkflowError, "has not been started"):
                missing.resume(snapshot_path)
