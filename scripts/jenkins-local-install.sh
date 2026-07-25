#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv="$root/.jenkins-local-venv"
python3 -m venv "$venv"
"$venv/bin/python" -m pip install --disable-pip-version-check --no-deps --no-build-isolation --editable "$root" >/dev/null
"$venv/bin/python" -c 'import agent_workflow; print(agent_workflow.__file__)' >/dev/null
printf 'local install: %s\n' "$venv"
