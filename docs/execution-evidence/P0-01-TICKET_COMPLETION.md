# Ticket completion: P0-01

- Added `skills/agent-workflow-orchestrator/SKILL.md` with decision, launch, control, recovery, review, tmux, native-subagent, and steering contracts.
- Cross-linked and corrected all three existing workflow skills.
- Installed all four skills into shared, Codex, and Claude discovery roots using owned symlinks.
- Updated uninstall ownership behavior, README, installation docs, P0 design record, and BKL-006 state.
- Added narrow installer and skill-contract tests.
- Focused gate: `PYTHONPATH=src python3 -m unittest tests.test_install_uninstall tests.test_skill_contracts -v` — passed.
- Source scope exception: `uninstall.sh` was changed because installer ownership must be reversible and safely tested; no runtime lifecycle code changed.
