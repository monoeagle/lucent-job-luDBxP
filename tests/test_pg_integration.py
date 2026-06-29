"""AP-63·S2b/S3 — optional live PostgreSQL integration test.

Runs only when LUCENT_PG_TEST_URL points at a reachable PostgreSQL with write
access; otherwise it skips, so the suite stays green without a PG instance.
Provisions a sequence + a materialized view + a function, reflects them through
the app's loader, and asserts all are captured — the real reflect path only PG
can verify. Example::

    LUCENT_PG_TEST_URL='postgresql+psycopg://user:pw@localhost:5432/db' \
        ./venv/bin/python -m pytest tests/test_pg_integration.py
"""
import os

import pytest
from sqlalchemy import create_engine, text

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader

_PG_URL = os.environ.get("LUCENT_PG_TEST_URL")
pytestmark = pytest.mark.skipif(not _PG_URL, reason="LUCENT_PG_TEST_URL not set")

_SEQ = "_lucent_it_seq"
_MV = "_lucent_it_mv"
_FN = "_lucent_it_fn"

# AP-63 Trigger-FF: trigger test objects
_TRG_TAB = "_lucent_it_trg_tab"
_TRG = "_lucent_it_trg"
_TRG_FN = "_lucent_it_trg_fn"


@pytest.fixture
def pg_objects():
    engine = create_engine(_PG_URL)
    ddl = [
        f"DROP MATERIALIZED VIEW IF EXISTS {_MV}",
        f"DROP SEQUENCE IF EXISTS {_SEQ}",
        f"DROP FUNCTION IF EXISTS {_FN}()",
        f"CREATE SEQUENCE {_SEQ}",
        f"CREATE MATERIALIZED VIEW {_MV} AS SELECT 1 AS n",
        f"CREATE OR REPLACE FUNCTION {_FN}() RETURNS int LANGUAGE sql AS 'SELECT 1'",
        f"CREATE TABLE IF NOT EXISTS {_TRG_TAB} (id int)",
        f"CREATE OR REPLACE FUNCTION {_TRG_FN}() RETURNS trigger LANGUAGE plpgsql "
        f"AS 'BEGIN RETURN NEW; END'",
        f"CREATE TRIGGER {_TRG} AFTER INSERT ON {_TRG_TAB} "
        f"FOR EACH ROW EXECUTE FUNCTION {_TRG_FN}()",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    yield
    with engine.begin() as conn:
        conn.execute(text(f"DROP TRIGGER IF EXISTS {_TRG} ON {_TRG_TAB}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {_TRG_TAB}"))
        conn.execute(text(f"DROP FUNCTION IF EXISTS {_TRG_FN}()"))
        conn.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {_MV}"))
        conn.execute(text(f"DROP SEQUENCE IF EXISTS {_SEQ}"))
        conn.execute(text(f"DROP FUNCTION IF EXISTS {_FN}()"))
    engine.dispose()


def test_pg_reflects_sequence_and_matview(pg_objects):
    schema = SqlAlchemyLoader(_PG_URL).load()
    assert _SEQ in {s.name for s in schema.sequences}
    mv = {m.name: m for m in schema.materialized_views}
    assert _MV in mv
    assert "n" in {c.name for c in mv[_MV].columns}


def test_pg_reflects_function(pg_objects):
    schema = SqlAlchemyLoader(_PG_URL).load()
    by = {r.name: r for r in schema.routines}
    assert _FN in by
    assert by[_FN].kind == "function"
    assert "SELECT 1" in by[_FN].sql


def test_pg_reflects_trigger(pg_objects):
    schema = SqlAlchemyLoader(_PG_URL).load()
    by_trg = {t.name: t for t in schema.triggers}
    assert _TRG in by_trg
    assert by_trg[_TRG].table == _TRG_TAB
    assert "TRIGGER" in by_trg[_TRG].sql.upper()
