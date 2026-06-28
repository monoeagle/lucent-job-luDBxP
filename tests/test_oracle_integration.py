"""AP-53 — optional live Oracle integration test.

Runs only when ``LUCENT_ORACLE_TEST_URL`` points at a reachable Oracle instance;
otherwise it skips, so the suite stays green without an Oracle backend. Example::

    LUCENT_ORACLE_TEST_URL='oracle+oracledb://user:pw@localhost:1521/?service_name=XEPDB1' \
        ./venv/bin/python -m pytest tests/test_oracle_integration.py

URL-building is covered by unit tests in ``test_connection.py``.
"""
import os

import pytest
from sqlalchemy import create_engine, text

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader

_ORACLE_URL = os.environ.get("LUCENT_ORACLE_TEST_URL")
_PARENT = "lucent_it_parent"
_CHILD = "lucent_it_child"


@pytest.mark.skipif(
    not _ORACLE_URL,
    reason="set LUCENT_ORACLE_TEST_URL to a reachable Oracle URL to run the live "
           "integration test",
)
def test_oracle_live_reflection_with_fk():
    """Provision a Parent/Child schema on Oracle and reflect its FK via the loader."""
    pytest.importorskip("oracledb")
    try:
        engine = create_engine(_ORACLE_URL)
        conn = engine.connect()
    except Exception as exc:  # driver missing / instance unreachable → skip
        pytest.skip(f"Oracle not reachable or driver missing: {exc}")

    def _drop():
        for name in (_CHILD, _PARENT):
            try:
                conn.execute(text(f"DROP TABLE {name}"))
            except Exception:
                pass

    try:
        _drop()
        conn.execute(text(f"CREATE TABLE {_PARENT} (id NUMBER PRIMARY KEY, name VARCHAR2(50))"))
        conn.execute(text(
            f"CREATE TABLE {_CHILD} (id NUMBER PRIMARY KEY, parent_id NUMBER, "
            f"CONSTRAINT fk_lucent_it FOREIGN KEY (parent_id) REFERENCES {_PARENT}(id))"))
        conn.commit()

        schema = SqlAlchemyLoader(_ORACLE_URL).load()
        by_name = {t.name.lower(): t for t in schema.tables}
        assert _CHILD in by_name and _PARENT in by_name
        child = by_name[_CHILD]
        assert len(child.foreign_keys) == 1
        assert child.foreign_keys[0].ref_table.lower() == _PARENT
    finally:
        _drop()
        conn.commit()
        conn.close()
        engine.dispose()
