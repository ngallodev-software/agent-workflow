from __future__ import annotations

import pytest


@pytest.mark.future
@pytest.mark.xfail(strict=True, reason="BKL-004: comparable real-executor cohorts and complete ledger evidence are not yet available")
def test_bkl_004_ledger_distinguishes_unplanned_evaluation_from_complete_comparable_cohort() -> None:
    # Acceptance contract: an unplanned evaluation remains explicit and non-comparable;
    # a comparable cohort requires sealed plan, scores, reports, trials, and provenance.
    pytest.fail("BKL-004 comparable cohort acceptance evidence is not implemented")


@pytest.mark.future
@pytest.mark.xfail(strict=True, reason="MCP-003/HARD-007: authenticated MCP mutation boundary is not yet implemented")
def test_mcp_003_mutation_requires_authenticated_principal_and_preserves_read_only_tools() -> None:
    # Acceptance contract: anonymous/caller-labelled mutation is denied, authenticated
    # principals are recorded immutably, and existing read-only metadata tools still work.
    pytest.fail("MCP-003 authenticated mutation boundary is not implemented")
