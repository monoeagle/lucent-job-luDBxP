"""AP-12 — optional live MSSQL integration test.

This test only runs when ``LUCENT_MSSQL_TEST_URL`` points at a reachable
SQL Server instance; otherwise it is skipped, so the suite stays green on
machines without an ODBC driver or an MSSQL instance. Example::

    LUCENT_MSSQL_TEST_URL='mssql+pyodbc://sa:Pass1!@localhost:1433/master\
?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes' \
        ./venv/bin/python -m pytest tests/test_mssql_integration.py

It exercises the real connect + reflect path (the part that can only be
verified against an actual MSSQL backend); the URL-building and driver-hint
logic are covered by unit tests in ``test_connection.py``.
"""
import os

import pytest

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.model import Schema, Table

_MSSQL_URL = os.environ.get("LUCENT_MSSQL_TEST_URL")


@pytest.mark.skipif(
    not _MSSQL_URL,
    reason="set LUCENT_MSSQL_TEST_URL to a reachable MSSQL URL to run the live "
           "integration test",
)
def test_mssql_live_reflection_smoke():
    """Connect to a real MSSQL instance and reflect a well-formed schema."""
    pytest.importorskip("pyodbc")
    try:
        schema = SqlAlchemyLoader(_MSSQL_URL).load()
    except ConnectionError as exc:
        # URL given but instance unreachable / ODBC driver missing → skip
        # instead of failing, so a partial environment still runs cleanly.
        pytest.skip(f"MSSQL not reachable or ODBC driver missing: {exc}")

    # Connect + reflect succeeded → the model must be well-formed (an empty
    # database is fine; we assert structure, not a particular table set).
    assert isinstance(schema, Schema)
    assert isinstance(schema.tables, tuple)
    assert isinstance(schema.views, tuple)
    for t in schema.tables:
        assert isinstance(t, Table)
        assert t.name
        assert isinstance(t.columns, tuple)
        assert isinstance(t.foreign_keys, tuple)
        for c in t.columns:
            assert c.name
