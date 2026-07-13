.PHONY: test shell-check compile validate-example validate

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

compile:
	python3 -m compileall -q src

shell-check:
	bash -n install.sh uninstall.sh scripts/*.sh bin/agent-workflow

validate-example:
	PYTHONPATH=src python3 -m agent_workflow pack validate examples/three-phase-pack

validate:
	./scripts/release-check.sh
