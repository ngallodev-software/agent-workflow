from __future__ import annotations

import pytest


@pytest.mark.future
@pytest.mark.xfail(
    strict=True,
    reason="IDX-006/HARD-006/SUP-003/BKL-004: privacy-governed analytical export and comparable cohort integration are not yet accepted",
)
def test_idx_006_exported_analytical_snapshot_is_reproducible_redacted_and_provenance_bound() -> None:
    # Installed-product journey contract: a policy-approved immutable analytical
    # snapshot can be reproduced byte-for-byte from verified indexed sources,
    # excludes prohibited free-form bodies, and binds every row to source digests.
    pytest.fail("IDX-006 privacy-governed analytical export is not implemented")


@pytest.mark.future
@pytest.mark.xfail(
    strict=True,
    reason="IDX-007: measured-scale byte-offset checkpoints and migration/capacity proof are not yet implemented",
)
def test_idx_007_discarded_checkpoints_rebuild_after_truncation_rotation_and_interrupted_migration() -> None:
    # Installed-product journey contract: checkpoints improve measured incremental
    # performance but remain disposable; truncation, rotation, interruption, and
    # migration recovery preserve exact replay and full rebuild equivalence.
    pytest.fail("IDX-007 measured-scale checkpoint implementation is not complete")
