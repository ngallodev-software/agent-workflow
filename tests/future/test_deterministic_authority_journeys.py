from __future__ import annotations

import pytest


@pytest.mark.future
@pytest.mark.xfail(strict=True, reason="HARD-004: broader future phase-gate journey remains a planning placeholder")
def test_hard_004_status_projection_cannot_change_launch_or_receipt_authority() -> None:
    # Installed-product journey contract: after launch, mutating status.json must neither alter
    # collector inputs nor the digest returned for the exact verified final receipt.
    pytest.fail("HARD-004 immutable launch/receipt authority is not implemented")


@pytest.mark.future
@pytest.mark.xfail(strict=True, reason="MSG-005: durable replay and restart idempotency are not yet implemented")
def test_msg_005_restart_replays_uncommitted_messages_once_without_duplicate_effects() -> None:
    # Installed-product journey contract: crash at each inbox/cursor boundary, restart, and
    # observe every durable event applied once while duplicate wakeups remain harmless.
    pytest.fail("MSG-005 restart/replay semantics are not implemented")
