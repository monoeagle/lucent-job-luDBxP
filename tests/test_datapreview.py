from core.datapreview import fetch_rows


def test_fetch_rows_with_schema_runs(inventory_url):
    # SQLite's real schema is "main"; a schema-qualified preview must execute.
    res = fetch_rows(inventory_url, "VirtualMachines",
                     {"VirtualMachines"}, limit=5, schema="main")
    assert "columns" in res and "rows" in res
