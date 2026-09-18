from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


def _load_helper():
    path = Path(__file__).parents[2] / "scripts" / "bump-version.py"
    spec = importlib.util.spec_from_file_location("bump_version", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_json_authorities_accept_four_space_indentation_and_bump(
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    root = tmp_path
    version = "0.10.0"
    policy = root / "release-policy.json"
    lock = root / "dependency-lock.json"
    policy.write_text(
        json.dumps(
            {"schema": "policy", "project": "agent-workflow", "version": version},
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    lock.write_text(
        json.dumps(
            {
                "schema": "lock",
                "project": "agent-workflow",
                "version": version,
                "packages": [{"version": "other"}],
            },
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )

    assert helper.authority_matches(policy, helper.JSON_VERSION) == [version]
    assert helper.authority_matches(lock, helper.JSON_VERSION) == [version]
    helper.ROOT = root
    helper.replace_authority(policy, helper.JSON_VERSION, version, "0.10.1")
    helper.replace_authority(lock, helper.JSON_VERSION, version, "0.10.1")

    assert json.loads(policy.read_text(encoding="utf-8"))["version"] == "0.10.1"
    assert json.loads(lock.read_text(encoding="utf-8"))["version"] == "0.10.1"
    assert (
        json.loads(lock.read_text(encoding="utf-8"))["packages"][0]["version"]
        == "other"
    )


def test_versioned_documentation_replaces_every_release_reference(
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    document = tmp_path / "INSTALLATION.md"
    document.write_text(
        "For version `0.10.1`:\nreleases/v0.10.1/install.sh\n--version v0.10.1\n",
        encoding="utf-8",
    )
    helper.REPLACE_ALL_VERSION_TEXT = frozenset({document})

    helper.replace_authority(
        document, re.compile(r"For version `([0-9.]+)`"), "0.10.1", "0.10.2"
    )

    assert "0.10.1" not in document.read_text(encoding="utf-8")
    assert document.read_text(encoding="utf-8").count("0.10.2") == 3
