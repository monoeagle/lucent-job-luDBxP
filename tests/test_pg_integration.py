"""AP-63·S2b — optional live PostgreSQL integration test.

Runs only when LUCENT_PG_TEST_URL points at a reachable PostgreSQL with write
access; otherwise it skips, so the suite stays green without a PG instance.
Provisions a sequence + a materialized view, reflects them through the app's
loader, and asserts both are captured — the real reflect path only PG can
verify. Example::

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


@pytest.fixture
def pg_objects():
    engine = create_engine(_PG_URL)
    ddl = [
        f"DROP MATERIALIZED VIEW IF EXISTS {_MV}",
        f"DROP SEQUENCE IF EXISTS {_SEQ}",
        f"CREATE SEQUENCE {_SEQ}",
        f"CREATE MATERIALIZED VIEW {_MV} AS SELECT 1 AS n",
    ]
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    yield
    with engine.begin() as conn:
        conn.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {_MV}"))
        conn.execute(text(f"DROP SEQUENCE IF EXISTS {_SEQ}"))
    engine.dispose()


def test_pg_reflects_sequence_and_matview(pg_objects):
    schema = SqlAlchemyLoader(_PG_URL).load()
    assert _SEQ in {s.name for s in schema.sequences}
    mv = {m.name: m for m in schema.materialized_views}
    assert _MV in mv
    assert "n" in {c.name for c in mv[_MV].columns}
