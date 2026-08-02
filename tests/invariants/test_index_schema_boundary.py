from __future__ import annotations

import sqlite3

from agent_workflow import index_store
from agent_workflow.index_schema import (
    INDEX_APPLICATION_ID,
    INDEX_SCHEMA_VERSION,
    migrate,
    validate_database_header,
)


def test_index_store_reexports_schema_identity_from_dedicated_module() -> None:
    assert index_store.INDEX_APPLICATION_ID == INDEX_APPLICATION_ID
    assert index_store.INDEX_SCHEMA_VERSION == INDEX_SCHEMA_VERSION


def test_schema_module_creates_and_validates_the_exact_owned_database() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        migrate(connection)
        assert validate_database_header(connection) == (
            INDEX_APPLICATION_ID,
            INDEX_SCHEMA_VERSION,
        )
        migration = connection.execute(
            "SELECT version, description FROM schema_migrations"
        ).fetchone()
        assert migration == (1, "initial rebuildable evidence projection")
        assert connection.execute(
            "SELECT value FROM index_metadata WHERE key='authority'"
        ).fetchone()[0] == "json-jsonl-sealed-receipts"
    finally:
        connection.close()
