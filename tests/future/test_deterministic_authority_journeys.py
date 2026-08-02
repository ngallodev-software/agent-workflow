from __future__ import annotations

import pytest


@pytest.mark.future
@pytest.mark.xfail(
    strict=True,
    reason=(
        "MSG-005: projection reconstruction and oversized-status replay acceptance "
        "remain open"
    ),
)
def test_msg_005_restart_replays_uncommitted_messages_once_without_duplicate_effects() -> None:
    # Installed-product journey contract: crash at each inbox/cursor boundary, restart, and
    # observe every durable event applied once while duplicate wakeups remain harmless.
    # Corrupt, inconsistent, or oversized rebuildable supervisor projections must be
    # diagnosed and reconstructed rather than trusted or allowed to raise.
    pytest.fail("MSG-005 restart/replay closeout is not yet accepted")
