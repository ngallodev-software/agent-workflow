from __future__ import annotations

import json
import subprocess
from pathlib import Path

from agent_workflow.messages import append_message


def test_installed_product_replays_durable_target_once_and_advances_cursor(
    installed_product, product_env, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    record = append_message(
        source,
        session_id="installed-source",
        direction="child_to_parent",
        kind="progress",
        actor="child",
        content="installed journey",
    )
    state = tmp_path / "state"
    target = tmp_path / "target.jsonl"
    script = """
import json
import os
import sys
from pathlib import Path
from agent_workflow.consumer_cursors import ConsumerBinding, CursorStore
from agent_workflow.messages import replay_messages

source = Path(sys.argv[1])
state = Path(sys.argv[2])
target_path = Path(sys.argv[3])
process_number = sys.argv[4]
binding = ConsumerBinding(consumer_id='installed-consumer', principal='child', source_journal_id='sha256:' + 'c' * 64)
store = CursorStore(state, binding)
records = replay_messages(source)

def target_effects():
    if not target_path.exists():
        return []
    return [json.loads(line) for line in target_path.read_text(encoding='utf-8').splitlines()]

def commit(record, source_id, digest):
    prior = next((item for item in target_effects() if item['source_message_id'] == source_id), None)
    if prior is not None:
        assert prior['source_message_digest'] == digest
        return prior
    receipt = {
        'committed': True,
        'receipt_id': 'installed-target',
        'source_message_id': source_id,
        'source_message_digest': digest,
        'semantic_effect': 'one-installed-target-effect',
    }
    with target_path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(receipt, sort_keys=True) + '\\n')
        stream.flush()
        os.fsync(stream.fileno())
    return receipt

result = store.process(records[0], disposition='applied', commit_effect=commit)
print(json.dumps({
    'process': process_number,
    'status': result['status'],
    'effects': len(target_effects()),
    'sequence': store.read()['last_committed_source_sequence'],
}))
"""
    source_record = json.loads((source / "messages.jsonl").read_text(encoding="utf-8"))
    assert source_record == record

    def run_process(number: str) -> dict:
        result = subprocess.run(
            [
                str(installed_product.python),
                "-c",
                script,
                str(source),
                str(state),
                str(target),
                number,
            ],
            env=product_env,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    first = run_process("first")
    second = run_process("restart")
    assert first == {"process": "first", "status": "advanced", "effects": 1, "sequence": 1}
    assert second == {"process": "restart", "status": "duplicate", "effects": 1, "sequence": 1}
    assert len(target.read_text(encoding="utf-8").splitlines()) == 1
