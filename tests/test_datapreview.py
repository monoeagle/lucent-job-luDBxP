import pytest

from sample_data.build_demo_db import build
from core.datapreview import fetch_rows


@pytest.fixture
def demo_url(tmp_path):
    db = tmp_path / "demo.db"
    build(str(db))
    return f"sqlite:///{db}"


def test_fetch_rows_returns_columns_and_data(demo_url):
    res = fetch_rows(demo_url, "Datacenter", {"Datacenter", "Cluster"})
    assert "Name" in res["columns"]
    assert len(res["rows"]) >= 1  # the demo has two datacenters


def test_fetch_rows_respects_limit(demo_url):
    res = fetch_rows(demo_url, "VirtualMachine", {"VirtualMachine"}, limit=2)
    assert len(res["rows"]) <= 2


def test_fetch_rows_rejects_unknown_object(demo_url):
    # An object not in the allow-list must never reach SQL execution.
    with pytest.raises(ValueError):
        fetch_rows(demo_url, "x'; DROP TABLE Cluster;--", {"Datacenter"})


def test_fetch_rows_with_schema_runs(inventory_url):
    # SQLite's real schema is "main"; a schema-qualified preview must execute.
    res = fetch_rows(inventory_url, "VirtualMachines",
                     {"VirtualMachines"}, limit=5, schema="main")
    assert "columns" in res and "rows" in res
