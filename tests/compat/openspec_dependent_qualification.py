"""Installed-product dependency qualification shared by fake and real upstream gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from agent_workflow.receipts import verify_seal_details


def qualify(cli: str, root: Path, repo: Path, pack: Path, *, count=3, fail_final=False):
    root.mkdir(parents=True, exist_ok=True)
    sequence = 0

    def call(*args, error=None):
        nonlocal sequence
        sequence += 1
        result = subprocess.run([cli, "--json", *map(str, args)], text=True, capture_output=True)
        (root / f"command-{sequence:03d}.json").write_text(json.dumps({
            "argv": list(map(str, args)), "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}, indent=2) + "\n")
        if error is not None:
            assert result.returncode != 0, result.stdout + result.stderr
            assert error in result.stderr, result.stdout + result.stderr
            return None
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    def write(name, data):
        path = root / name
        path.write_text(json.dumps(data, indent=2) + "\n")
        return path

    task_ids = [f"openspec-add-rate-limit-1-{i}" for i in range(1, count + 1)]
    # C depends explicitly on A and B; B consumes A, C consumes B.
    deps = {task: task_ids[:index] for index, task in enumerate(task_ids)}
    transition = [{"id": "prefix-compiles", "argv": [shutil.which("python3"), "-B", "-c",
                  "import ast,pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('src').glob('*.py')]"],
                   "cwd": ".", "timeout_seconds": 30}]
    expression = ("from server import request; assert request(1, 2) == 200 and request(2, 2) == 429"
                  if count == 3 else "from rate_response import response; assert response(1, 2) == 200 and response(2, 2) == 429")
    combined = [{"id": "combined-behavior", "argv": [shutil.which("python3"), "-B", "-c",
                "import sys; sys.path.insert(0, 'src'); " + ("raise SystemExit(9)" if fail_final else expression)],
                 "cwd": ".", "timeout_seconds": 30}]
    dependencies = write("dependencies.json", deps)
    commands = write("commands.json", transition)
    final_commands = write("final-commands.json", combined)
    chain = root / "chain"

    def create(dest=chain, dependencies=dependencies):
        return ("worktree", "chain-create", repo, "--pack", pack, "--dependencies", dependencies,
                "--commands", commands, "--final-commands", final_commands, "--output", dest,
                "--actor", "qualification-host", "--reason", "Explicit dependent task qualification", "--tier", "low")

    for label, bad, message in (
        ("missing", {task_ids[0]: ["unknown"]}, "missing predecessor"),
        ("self", {task_ids[0]: [task_ids[0]]}, "self-dependency"),
        ("cycle", {task_ids[0]: [task_ids[1]], task_ids[1]: [task_ids[0]]}, "cyclic"),
    ):
        call(*create(root / f"bad-{label}", write(f"{label}.json", bad)), error=message)
    plan = call(*create())
    assert plan["order"] == task_ids
    frozen_planning = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (repo / "openspec").rglob("*") if p.is_file()}
    worker = root / "worker.py"
    worker.write_text('''import json, subprocess, sys
from pathlib import Path
cli, run_id, task, output = sys.argv[1:]
if task.endswith('1-1'):
    code = 'def allow(count, limit):\\n    return count < limit\\n'
elif task.endswith('1-2'):
    sys.path.insert(0, 'src')
    from rate_limiter import allow
    assert allow(1, 2) and not allow(2, 2)
    code = 'from rate_limiter import allow\\ndef response(count, limit):\\n    return 200 if allow(count, limit) else 429\\n'
else:
    sys.path.insert(0, 'src')
    from rate_response import response
    assert response(1, 2) == 200 and response(2, 2) == 429
    code = 'from rate_response import response\\ndef request(count, limit):\\n    return response(count, limit)\\n'
Path(output).write_text(code)
subprocess.run(['git', 'add', '--', output], check=True)
subprocess.run(['git', 'commit', '-qm', 'implement ' + task], check=True)
r = subprocess.run([cli, '--json', 'agent', 'finish', run_id, '--result', 'completed'], text=True, capture_output=True)
print(r.stdout); print(r.stderr, file=sys.stderr)
assert r.returncode == 0
assert json.loads(r.stdout)['verification'][0]['ok']
''')
    state = Path(os.environ["XDG_STATE_HOME"]) / "agent-workflow/runs"
    seals = []
    heads = []
    baseline = plan["planning_revision"]
    for index, task in enumerate(task_ids):
        run_id = f"dependent-{root.name}-{index}"
        output = ["src/rate_limiter.py", "src/rate_response.py", "src/server.py"][index]
        if index:
            # Reopening every command in a new process proves state is not in memory.
            status = call("worktree", "chain-status", chain)
            assert status["accepted_tasks"] == index and not status["final_accepted"]
            assert status["execution_revision"] == baseline
            previous_patch = state / f"dependent-{root.name}-{index-1}" / "patch.diff"
            old = previous_patch.read_bytes()
            previous_patch.chmod(0o644); previous_patch.write_bytes(old + b"tampered")
            call("worktree", "chain-prepare", chain, run_id, "--", "python3", error="sealed artifact")
            previous_patch.write_bytes(old); previous_patch.chmod(0o444)
        (repo / "dirty-sentinel").write_text("dirty")
        call("worktree", "chain-prepare", chain, run_id, "--", "python3", error="repository must be clean")
        (repo / "dirty-sentinel").unlink()
        call("worktree", "chain-prepare", chain, run_id, "--", "python3", worker, cli, run_id, task, output)
        call("worktree", "chain-prepare", chain, run_id + "-duplicate", "--", "python3", error="already reserved")
        reservation_path = chain / f"task-{index:04d}.json"
        original = reservation_path.read_bytes()
        reservation = json.loads(original)
        changed = dict(reservation, execution_revision="0" * 40)
        reservation_path.chmod(0o644); reservation_path.write_text(json.dumps(changed))
        call("worktree", "chain-status", chain, error="incorrect or stale execution baseline")
        reservation_path.write_bytes(original); reservation_path.chmod(0o444)
        worktree = Path(reservation["worktree"])
        assert subprocess.check_output(["git", "-C", str(worktree), "rev-parse", "HEAD"], text=True).strip() == baseline
        planning_path = next(p for p in worktree.rglob("openspec/changes/*/tasks.md"))
        planning_bytes = planning_path.read_bytes()
        planning_path.write_bytes(planning_bytes + b"\nchanged")
        # Public native-job preparation still rejects changed planning/dirty sources.
        call("agent-run", "prepare", run_id + "-dirty", worktree, pack / "phase-0/tickets" / f"{task}.md",
             "--pack", pack, "--job", f"jobs/{task}.json", "--tier", "low", "--worker-mode", "external", "--", "python3",
             error="source worktree must be clean" if not index else "revision does not match")
        bound = call("agent-run", "bind-external", run_id, "dependency-fixture", "worker")
        generation = str(bound["generation"])
        call("agent-run", "start-external", run_id, "dependency-fixture", "worker", "--generation", generation,
             error="source worktree must be clean")
        planning_path.write_bytes(planning_bytes)
        if index:
            subprocess.run(["git", "-C", str(worktree), "checkout", "--detach", plan["planning_revision"]], check=True, capture_output=True)
            call("agent-run", "start-external", run_id, "dependency-fixture", "worker", "--generation", generation,
                 error="revision does not match")
            subprocess.run(["git", "-C", str(worktree), "checkout", "--detach", baseline], check=True, capture_output=True)
        call("agent-run", "start-external", run_id, "dependency-fixture", "worker", "--generation", generation)
        command = json.loads((state / run_id / "command.json").read_text())
        completed = subprocess.run(command["argv"], cwd=worktree, text=True, capture_output=True, timeout=60)
        write(f"worker-{index}.json", {"stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode})
        assert completed.returncode == 0, completed.stdout + completed.stderr
        call("agent-run", "external-exit", run_id, "--generation", generation,
             "--actor", "qualification-host", "--reason", "Observed real fixture exit")
        call("agent-run", "finalize", run_id)
        # No task can advance without host review and acceptance.
        call("worktree", "chain-advance", chain, error="not host-accepted")
        assert not (chain / f"integration-{index:04d}").exists()
        call("agent-run", "review", run_id, "--actor", "qualification-host", "--reason", "Review scoped dependent result")
        call("agent-run", "accept", run_id, "--actor", "qualification-host", "--reason", "Accept verified task result")
        final, seal = verify_seal_details(state / run_id)
        patch = (state / run_id / "patch.diff").read_bytes()
        head = json.loads((state / run_id / "completion.json").read_text())["head_revision"]
        expected = subprocess.check_output(["git", "-C", str(worktree), "diff", "--no-ext-diff", "--no-textconv", "--binary", "--full-index", baseline, head])
        assert expected and patch == expected
        assert "jobs/execution-binding.json" in {a["path"] for a in final["artifacts"]}
        seals.append(seal); heads.append(head)
        advanced = call("worktree", "chain-advance", chain)
        assert advanced["head_revision"] == head and advanced["purpose"] == "transition"
        call("worktree", "chain-advance", chain, error="no unintegrated reserved task")
        # Tamper with archived predecessor evidence, then restore exact sealed bytes.
        archived = chain / f"integration-{index:04d}/inputs" / run_id / "patch.diff"
        original_patch = archived.read_bytes()
        archived.chmod(0o644); archived.write_bytes(b"tampered")
        call("worktree", "chain-status", chain, error="artifact mismatch")
        archived.write_bytes(original_patch); archived.chmod(0o444)
        baseline = head
        for previous, digest in enumerate(seals):
            assert verify_seal_details(state / f"dependent-{root.name}-{previous}")[1] == digest
    recovered = call("worktree", "chain-status", chain)
    assert recovered["accepted_tasks"] == count and not recovered["final_accepted"]
    if fail_final:
        call("worktree", "chain-accept", chain, error="combined acceptance command failed")
        rejected = json.loads((chain / "final/integration-receipt.json").read_text())
        assert rejected["status"] == rejected["decision"] == "rejected"
        assert not (chain.parent / (chain.name + "-final")).exists()
        call("worktree", "chain-status", chain, error="invalid or failed combined chain acceptance")
        result = {"final_accepted": False, "rejected_command": True, "heads": heads}
    else:
        final = call("worktree", "chain-accept", chain)
        assert final["purpose"] == "final" and final["head_revision"] == heads[-1]
        assert call("worktree", "chain-status", chain)["final_accepted"]
        call("worktree", "chain-accept", chain, error="already finally accepted")
        archived_final = root / "archived-final"
        shutil.copytree(chain / "final", archived_final)
        offline_repo = repo.with_name(repo.name + "-offline")
        repo.rename(offline_repo)
        try:
            # Original Git storage/worktrees are unavailable during archive replay.
            verified = call("worktree", "integration-verify", archived_final)
            assert verified["head_revision"] == heads[-1]
        finally:
            offline_repo.rename(repo)
        result = {"final_accepted": True, "heads": heads, "receipt_sha256": final["receipt_sha256"],
                  "seal_sha256": seals, "accurate_nonempty_patches": count, "archived_replay": True}
    assert frozen_planning == {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (repo / "openspec").rglob("*") if p.is_file()}
    write("qualification-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cli")
    parser.add_argument("root", type=Path)
    parser.add_argument("repo", type=Path)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--fail-final", action="store_true")
    args = parser.parse_args()
    print(json.dumps(qualify(args.cli, args.root, args.repo, args.pack,
                             count=args.count, fail_final=args.fail_final), indent=2))
