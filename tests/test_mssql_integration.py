"""AP-12 — optional live MSSQL integration test.

Runs only when ``LUCENT_MSSQL_TEST_URL`` points at a reachable SQL Server with
write access; otherwise it skips, so the suite stays green on machines without
an ODBC driver or an MSSQL instance. Example::

    LUCENT_MSSQL_TEST_URL='mssql+pyodbc://sa:Pass1!@localhost:1433/master\
?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes' \
        ./venv/bin/python -m pytest tests/test_mssql_integration.py

The test provisions a tiny Parent/Child schema (one foreign key), reflects it
through the app's loader, and asserts the FK edge is captured — i.e. it
exercises the real connect + reflect path that can only be verified against an
actual MSSQL backend. URL-building and the driver-hint message are covered by
unit tests in ``test_connection.py``.
"""
import os

import pytest
from sqlalchemy import create_engine, text

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader

_MSSQL_URL = os.environ.get("LUCENT_MSSQL_TEST_URL")
_PARENT = "_lucent_it_parent"
_CHILD = "_lucent_it_child"

_DROP = (f"IF OBJECT_ID('{_CHILD}') IS NOT NULL DROP TABLE {_CHILD}; "
         f"IF OBJECT_ID('{_PARENT}') IS NOT NULL DROP TABLE {_PARENT};")


@pytest.mark.skipif(
    not _MSSQL_URL,
    reason="set LUCENT_MSSQL_TEST_URL to a reachable MSSQL URL to run the live "
           "integration test",
)
def test_mssql_live_reflection_with_fk():
    """Provision a Parent/Child schema on MSSQL and reflect its FK via the loader."""
    pytest.importorskip("pyodbc")
    try:
        engine = create_engine(_MSSQL_URL, isolation_level="AUTOCOMMIT")
        conn = engine.connect()
    except Exception as exc:  # driver missing / instance unreachable → skip
        pytest.skip(f"MSSQL not reachable or ODBC driver missing: {exc}")

    try:
        conn.execute(text(_DROP))
        conn.execute(text(f"CREATE TABLE {_PARENT} (id INT PRIMARY KEY, name NVARCHAR(50))"))
        conn.execute(text(
            f"CREATE TABLE {_CHILD} (id INT PRIMARY KEY, parent_id INT, "
            f"CONSTRAINT fk_lucent_it FOREIGN KEY (parent_id) REFERENCES {_PARENT}(id))"
        ))

        schema = SqlAlchemyLoader(_MSSQL_URL).load()
        by_name = {t.name: t for t in schema.tables}
        assert _PARENT in by_name and _CHILD in by_name

        child = by_name[_CHILD]
        assert child.primary_key == ("id",)
        assert {c.name for c in child.columns} == {"id", "parent_id"}
        assert len(child.foreign_keys) == 1
        fk = child.foreign_keys[0]
        assert fk.ref_table == _PARENT
        assert fk.columns == ("parent_id",)
        assert fk.ref_columns == ("id",)
    finally:
        conn.execute(text(_DROP))
        conn.close()
        engine.dispose()
