"""AP-53/AP-63·S3 — optional live Oracle integration test.

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

# AP-63·S3: routine + synonym test objects (uppercase — Oracle catalog is case-sensitive)
_RTN_TAB = "LUCENT_IT_RTN_TAB"
_FN_ORA = "LUCENT_IT_FN"
_PKG_ORA = "LUCENT_IT_PKG"
_SYN_ORA = "LUCENT_IT_SYN"

# AP-63 Trigger-FF: trigger test objects (uppercase — Oracle catalog is case-sensitive)
_TRG_TAB_ORA = "LUCENT_IT_TRG_TAB"
_TRG_ORA = "LUCENT_IT_TRG"


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


@pytest.mark.skipif(
    not _ORACLE_URL,
    reason="set LUCENT_ORACLE_TEST_URL to a reachable Oracle URL to run the live "
           "integration test",
)
def test_oracle_reflects_routines_and_synonyms():
    """Provision a function + package + synonym on Oracle and reflect via the loader."""
    pytest.importorskip("oracledb")
    try:
        engine = create_engine(_ORACLE_URL)
        conn = engine.connect()
    except Exception as exc:
        pytest.skip(f"Oracle not reachable or driver missing: {exc}")

    def _drop():
        for obj, typ in [
            (_SYN_ORA, "SYNONYM"),
            (_PKG_ORA, "PACKAGE"),
            (_FN_ORA, "FUNCTION"),
            (_RTN_TAB, "TABLE"),
        ]:
            try:
                conn.execute(text(f"DROP {typ} {obj}"))
            except Exception:
                pass

    try:
        _drop()
        conn.execute(text(f"CREATE TABLE {_RTN_TAB} (id NUMBER PRIMARY KEY)"))
        conn.execute(text(
            f"CREATE OR REPLACE FUNCTION {_FN_ORA} RETURN NUMBER AS "
            f"BEGIN RETURN 1; END;"
        ))
        conn.execute(text(
            f"CREATE OR REPLACE PACKAGE {_PKG_ORA} AS PROCEDURE p; END {_PKG_ORA};"
        ))
        conn.execute(text(f"CREATE OR REPLACE SYNONYM {_SYN_ORA} FOR {_RTN_TAB}"))
        conn.commit()

        schema = SqlAlchemyLoader(_ORACLE_URL).load()

        by_rtn = {r.name: r for r in schema.routines}
        assert _FN_ORA in by_rtn, f"{_FN_ORA} not in routines: {list(by_rtn)}"
        assert by_rtn[_FN_ORA].kind == "function"
        assert by_rtn[_FN_ORA].sql, "function sql should be non-empty"

        assert _PKG_ORA in by_rtn, f"{_PKG_ORA} not in routines: {list(by_rtn)}"
        assert by_rtn[_PKG_ORA].kind == "package"

        by_syn = {s.name: s for s in schema.synonyms}
        assert _SYN_ORA in by_syn, f"{_SYN_ORA} not in synonyms: {list(by_syn)}"
        assert by_syn[_SYN_ORA].target == _RTN_TAB
    finally:
        _drop()
        conn.commit()
        conn.close()
        engine.dispose()


@pytest.mark.skipif(
    not _ORACLE_URL,
    reason="set LUCENT_ORACLE_TEST_URL to a reachable Oracle URL to run the live "
           "integration test",
)
def test_oracle_reflects_trigger():
    """Provision a table + BEFORE-INSERT trigger on Oracle and reflect via loader."""
    pytest.importorskip("oracledb")
    try:
        engine = create_engine(_ORACLE_URL)
        conn = engine.connect()
    except Exception as exc:
        pytest.skip(f"Oracle not reachable or driver missing: {exc}")

    def _drop():
        for obj, typ in [
            (_TRG_ORA, "TRIGGER"),
            (_TRG_TAB_ORA, "TABLE"),
        ]:
            try:
                conn.execute(text(f"DROP {typ} {obj}"))
            except Exception:
                pass

    try:
        _drop()
        conn.execute(text(f"CREATE TABLE {_TRG_TAB_ORA} (id NUMBER PRIMARY KEY)"))
        conn.execute(text(
            f"CREATE OR REPLACE TRIGGER {_TRG_ORA} "
            f"BEFORE INSERT ON {_TRG_TAB_ORA} FOR EACH ROW BEGIN NULL; END;"
        ))
        conn.commit()

        schema = SqlAlchemyLoader(_ORACLE_URL).load()
        by_trg = {t.name: t for t in schema.triggers}
        assert _TRG_ORA in by_trg, f"{_TRG_ORA} not in triggers: {list(by_trg)}"
        assert by_trg[_TRG_ORA].table == _TRG_TAB_ORA
        assert by_trg[_TRG_ORA].sql, "trigger sql should be non-empty"
    finally:
        _drop()
        conn.commit()
        conn.close()
        engine.dispose()
