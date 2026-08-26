"""Opt-in bounded hierarchical orchestration authority primitives.

Immutable contract authority, append-only local journals, deterministic replay,
and digest-sealed team/root receipts are implemented here. Runtime hosting,
messaging, scheduling, and recovery remain independently gated.
"""

from .contracts import (
    HIERARCHY_SCHEMA,
    TEAM_DELEGATION_SCHEMA,
    install_contract_set,
    read_contract_set,
    seal_hierarchy_contract,
    seal_team_delegation_contract,
    validate_hierarchy_contract,
    validate_team_delegation_contract,
)

from .journals import (
    JOURNAL_RECORD_SCHEMA,
    append_journal_record,
    read_journal,
    replay_authority_state,
)
from .receipts import (
    ROOT_RECEIPT_SCHEMA,
    TEAM_RECEIPT_SCHEMA,
    EvidenceReference,
    JournalReference,
    create_root_receipt,
    create_team_receipt,
    verify_root_receipt,
    verify_team_receipt,
)

__all__ = [
    "HIERARCHY_SCHEMA",
    "JOURNAL_RECORD_SCHEMA",
    "ROOT_RECEIPT_SCHEMA",
    "TEAM_DELEGATION_SCHEMA",
    "TEAM_RECEIPT_SCHEMA",
    "EvidenceReference",
    "JournalReference",
    "append_journal_record",
    "create_root_receipt",
    "create_team_receipt",
    "install_contract_set",
    "read_contract_set",
    "read_journal",
    "replay_authority_state",
    "seal_hierarchy_contract",
    "seal_team_delegation_contract",
    "validate_hierarchy_contract",
    "validate_team_delegation_contract",
    "verify_root_receipt",
    "verify_team_receipt",
]
