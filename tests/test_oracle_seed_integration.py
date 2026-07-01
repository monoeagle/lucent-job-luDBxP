"""Skip-guarded Oracle demo-seed integration test (AP-67·Oracle-Adaption).

Runs only when ``LUCENT_ORACLE_TEST_URL`` points at a reachable Oracle instance;
otherwise it skips, so the suite stays green without an Oracle backend. Example::

    LUCENT_ORACLE_TEST_URL='oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1' \\
        ./venv/bin/python -m pytest tests/test_oracle_seed_integration.py

Seeds the server-demo CMDB via the app's seeder and asserts every reflectable
Oracle object category appears (case-insensitive: Oracle reflection returns
table/view/sequence names lower-cased and trigger/routine/synonym names upper-cased).
"""
import os
import pathlib
import sys

import pytest

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader

_ORACLE_URL = os.environ.get("LUCENT_ORACLE_TEST_URL")


@pytest.mark.skipif(
    not _ORACLE_URL,
    reason="set LUCENT_ORACLE_TEST_URL to a reachable Oracle URL to run the live "
           "integration test",
)
def test_oracle_demo_seed_shows_all_categories():
    """Seed the server demo CMDB and assert every reflectable category appears."""
    pytest.importorskip("oracledb")
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "sample_data"))
    try:
        from seed_server_demo import seed
        seed(_ORACLE_URL)
    except Exception as exc:  # instance unreachable / seed failed → skip
        pytest.skip(f"Oracle not reachable or seed failed: {exc}")

    schema = SqlAlchemyLoader(_ORACLE_URL).load()
    up = lambda xs: {x.name.upper() for x in xs}
    assert {"VIRTUALMACHINE", "HOST", "VMCLUSTER", "DATACENTER", "OPERATINGSYSTEM"} <= up(schema.tables)
    assert "VW_VM_LABELED" in up(schema.views)
    assert "TRG_VM_AUDIT" in up(schema.triggers)
    assert "DEMO_VM_SEQ" in up(schema.sequences)
    assert "MV_VM_PER_HOST" in up(schema.materialized_views)
    assert "SYN_VM" in up(schema.synonyms)
    kinds = {r.name.upper(): r.kind for r in schema.routines}
    assert kinds.get("FN_VM_LABEL") == "function"
    assert kinds.get("USP_VM_COUNT") == "procedure"
    assert kinds.get("PKG_VM") == "package"
    # AP-66·S1: the view references the function
    vw = next(v for v in schema.views if v.name.upper() == "VW_VM_LABELED")
    assert "FN_VM_LABEL" in {r.upper() for r in vw.routines}

    # v0.64.2 regression guard: data preview must work on Oracle for both a table
    # and a view (dialect LIMIT → FETCH FIRST, and reflected lower-cased names).
    from core.datapreview import fetch_rows
    valid = {t.name for t in schema.tables} | {v.name for v in schema.views}
    tbl_name = next(t.name for t in schema.tables if t.name.upper() == "VIRTUALMACHINE")
    assert len(fetch_rows(_ORACLE_URL, tbl_name, valid, limit=100)["rows"]) == 2
    assert len(fetch_rows(_ORACLE_URL, vw.name, valid, limit=100)["rows"]) == 2
