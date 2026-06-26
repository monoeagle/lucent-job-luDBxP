import pytest
from web import create_app
from sample_data.build_demo_db import build


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


@pytest.fixture
def demo_url(tmp_path):
    """Demo CMDB SQLite URL with real data rows (for /api/joinpath/run tests)."""
    db = tmp_path / "demo_api.db"
    build(str(db))
    return f"sqlite:///{db}"


def test_schema_endpoint_returns_tables(client, inventory_url):
    resp = client.post("/api/schema", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    names = {t["name"] for t in resp.get_json()["tables"]}
    assert "VirtualMachines" in names


def test_connect_sqlite_returns_url(client, inventory_url):
    path = inventory_url.replace("sqlite:///", "")
    resp = client.post("/api/connect", json={"db_type": "sqlite", "filepath": path})
    assert resp.status_code == 200
    assert resp.get_json()["connection_url"].startswith("sqlite:///")


def test_connect_missing_host_returns_400(client):
    resp = client.post("/api/connect", json={"db_type": "postgresql", "database": "d"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_connections_save_list_delete_without_password(client, tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "CONFIG_JSON", str(tmp_path / "settings.json"))
    save = client.post("/api/connections", json={
        "name": "prod", "db_type": "postgresql", "host": "h",
        "database": "cmdb", "user": "admin", "password": "SECRET"})
    assert save.status_code == 200
    conns = client.get("/api/connections").get_json()["connections"]
    saved = next(c for c in conns if c["name"] == "prod")
    assert saved["host"] == "h" and saved["database"] == "cmdb"
    assert "password" not in saved  # password is never persisted
    client.delete("/api/connections", json={"name": "prod"})
    assert client.get("/api/connections").get_json()["connections"] == []


def test_connect_from_saved_sqlite_round_trip(client, demo_url, tmp_path, monkeypatch):
    # AP-10: the topbar picker connects directly from a saved (passwordless)
    # connection. Round-trip: save -> list -> connect using the saved entry
    # verbatim (exactly what connectSaved() posts to /api/connect).
    import config
    monkeypatch.setattr(config, "CONFIG_JSON", str(tmp_path / "settings.json"))
    path = demo_url.replace("sqlite:///", "")
    client.post("/api/connections", json={
        "name": "demo", "db_type": "sqlite", "filepath": path})
    saved = next(c for c in client.get("/api/connections").get_json()["connections"]
                 if c["name"] == "demo")
    resp = client.post("/api/connect", json=saved)
    assert resp.status_code == 200
    assert resp.get_json()["connection_url"] == demo_url


def test_info_endpoint_returns_metadata_and_stack(client):
    data = client.get("/api/info").get_json()
    assert data["name"] == "LucentTools DB Explorer"
    assert data["version"]
    assert "Tobias" in data["author"]
    stack_names = {s["name"] for s in data["stack"]}
    assert {"Python", "Flask", "SQLAlchemy", "NetworkX", "Cytoscape.js"} <= stack_names


def test_schema_returns_column_details_fks_and_views(client, inventory_url):
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    vm = next(t for t in data["tables"] if t["name"] == "VirtualMachines")
    vmid = next(c for c in vm["columns"] if c["name"] == "VMID")
    assert vmid["pk"] is True and vmid["type"]
    net_fk = next(fk for fk in vm["foreign_keys"] if fk["ref_table"] == "Networks")
    assert net_fk["columns"] == ["NetworkID"]        # list form (composite-ready)
    assert net_fk["ref_columns"] == ["NetworkID"]
    views = {v["name"] for v in data["views"]}
    assert "VMNetworks" in views
    vmn = next(v for v in data["views"] if v["name"] == "VMNetworks")
    assert "SELECT" in vmn["definition"].upper()


def test_schema_includes_table_ddl(client, inventory_url):
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    vm = next(t for t in data["tables"] if t["name"] == "VirtualMachines")
    assert "CREATE TABLE VirtualMachines" in vm["ddl"]


def test_data_endpoint_returns_columns(client, inventory_url):
    resp = client.post("/api/data", json={
        "connection_url": inventory_url, "object": "Networks"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "VLAN" in data["columns"]
    assert isinstance(data["rows"], list)


def test_data_endpoint_unknown_object_returns_400(client, inventory_url):
    resp = client.post("/api/data", json={
        "connection_url": inventory_url, "object": "DoesNotExist"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_endpoint_returns_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    assert "SELECT" in paths[0]["sql"]
    assert "VirtualMachines" in paths[0]["tables"]
    # edges describe the actual join steps (for graph highlighting)
    assert paths[0]["edges"]
    assert all(len(e) == 2 for e in paths[0]["edges"])


def test_joinpath_no_connection_returns_400(client):
    resp = client.post("/api/joinpath", json={
        "connection_url": "sqlite:////nope/x.db",
        "start": {"table": "A", "column": "x"},
        "target": {"table": "B", "column": "y"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_missing_start_returns_400(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_unknown_table_returns_400(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "DoesNotExist", "column": "x"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_schema_empty_connection_returns_clear_message(client):
    # A blank URL must yield a helpful message, not the raw SQLAlchemy
    # "Could not parse URL" internals.
    resp = client.post("/api/schema", json={"connection_url": "   "})
    assert resp.status_code == 400
    assert "Connection-URL" in resp.get_json()["error"]


def test_joinpath_empty_connection_returns_clear_message(client):
    resp = client.post("/api/joinpath", json={
        "connection_url": "",
        "start": {"table": "A", "column": "x"},
        "target": {"table": "B", "column": "y"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "Connection-URL" in resp.get_json()["error"]


def test_graph_endpoint_returns_nodes_and_edges(client, inventory_url):
    resp = client.post("/api/graph", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    data = resp.get_json()
    node_ids = {n["id"] for n in data["nodes"]}
    assert node_ids == {
        "Networks", "VirtualMachines", "OperatingSystems", "VMwareCluster",
    }
    pairs = {frozenset((e["source"], e["target"])) for e in data["edges"]}
    assert frozenset(("VirtualMachines", "Networks")) in pairs


def test_graph_empty_connection_returns_400(client):
    resp = client.post("/api/graph", json={"connection_url": ""})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_graph_without_implied_has_no_edges_in_nofk(client, inventory_nofk_url):
    resp = client.post("/api/graph", json={"connection_url": inventory_nofk_url})
    assert resp.get_json()["edges"] == []


def test_graph_with_implied_adds_marked_edges(client, inventory_nofk_url):
    resp = client.post("/api/graph", json={
        "connection_url": inventory_nofk_url, "include_implied": True})
    edges = resp.get_json()["edges"]
    assert edges and all(e["implied"] for e in edges)


def test_joinpath_with_implied_finds_path(client, inventory_nofk_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_nofk_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [], "include_implied": True})
    assert resp.status_code == 200
    assert resp.get_json()["paths"]


def test_joinpath_without_implied_no_path_in_nofk(client, inventory_nofk_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_nofk_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": []})
    assert resp.status_code == 400


def test_joinpath_unknown_column_returns_400(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "GhostColumn"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_extra_selects_appear_in_sql(client, inventory_url):
    """Extra selects whose table is on the join path appear in the SELECT clause."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "extra_selects": [{"table": "VirtualMachines", "column": "VMID"}],
        "filters": [],
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    # VirtualMachines is always on this path, so VMID must appear in every path's SQL
    for p in paths:
        assert "VirtualMachines.VMID" in p["sql"]
    # Start and target columns must still be present
    assert "Networks.VLAN" in paths[0]["sql"]
    assert "VMwareCluster.ClusterID" in paths[0]["sql"]


def test_joinpath_extra_select_off_path_excluded(client, inventory_url):
    """Extra selects from a table not on this join path are silently excluded."""
    # Path Networks -> VirtualMachines -> VMwareCluster does NOT include OperatingSystems
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "extra_selects": [{"table": "OperatingSystems", "column": "OS_Family"}],
        "filters": [],
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    for p in paths:
        assert "OperatingSystems" not in p["tables"]
        assert "OperatingSystems.OS_Family" not in p["sql"]


def test_joinpath_extra_select_unknown_column_returns_400(client, inventory_url):
    """An extra select referencing an unknown column is rejected with 400."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "extra_selects": [{"table": "VirtualMachines", "column": "NoSuchColumn"}],
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ===== AP-3: SQL-options package =====

def test_joinpath_ap3_distinct_orderby_limit_in(client, inventory_url):
    """E2E: DISTINCT + ORDER BY + LIMIT + IN filter all appear in the SQL."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [
            {"table": "VirtualMachines", "column": "VMID",
             "op": "IN", "value": ["1", "2", "3"]},
        ],
        "distinct": True,
        "order_by": [{"table": "VirtualMachines", "column": "VMID", "dir": "DESC"}],
        "limit": 50,
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    sql = paths[0]["sql"]
    # DISTINCT
    assert "SELECT DISTINCT" in sql
    # IN with parameterized placeholders
    assert "IN (" in sql
    assert ":p0_0" in sql
    assert ":p0_1" in sql
    assert ":p0_2" in sql
    # ORDER BY
    assert "ORDER BY" in sql
    assert "VirtualMachines.VMID DESC" in sql
    # LIMIT
    assert "LIMIT 50" in sql
    # ORDER BY before LIMIT
    assert sql.index("ORDER BY") < sql.index("LIMIT 50")
    # Values are parameterized, never inlined
    params = paths[0]["params"]
    assert params.get("p0_0") == "1"
    assert params.get("p0_1") == "2"
    assert params.get("p0_2") == "3"


def test_joinpath_ap3_is_null_filter(client, inventory_url):
    """IS NULL filter produces no placeholder and renders IS NULL in WHERE."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [
            {"table": "VirtualMachines", "column": "OSID",
             "op": "IS NULL", "value": None},
        ],
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    sql = paths[0]["sql"]
    assert "VirtualMachines.OSID IS NULL" in sql
    assert not paths[0]["params"]  # no params for IS NULL


def test_joinpath_ap3_between_filter(client, inventory_url):
    """BETWEEN filter uses two named placeholders."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [
            {"table": "VirtualMachines", "column": "VMID",
             "op": "BETWEEN", "value": ["1", "100"]},
        ],
    })
    assert resp.status_code == 200
    sql = resp.get_json()["paths"][0]["sql"]
    assert "BETWEEN :p0_lo AND :p0_hi" in sql


def test_joinpath_ap3_invalid_direction_returns_400(client, inventory_url):
    """Invalid ORDER BY direction is rejected with 400."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
        "order_by": [{"table": "VirtualMachines", "column": "VMID", "dir": "SIDEWAYS"}],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# ===== /api/joinpath/run =====

def test_joinpath_run_returns_columns_and_rows(client, demo_url):
    """/api/joinpath/run returns columns + data rows for a known demo path."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Network", "column": "VLAN"},
        "target": {"table": "Cluster", "column": "Name"},
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "columns" in data and "rows" in data and "sql" in data
    assert "VLAN" in data["columns"]
    assert "Name" in data["columns"]
    assert isinstance(data["rows"], list)
    assert len(data["rows"]) >= 1  # demo has matching rows (Networks + Clusters share DCs)


def test_joinpath_run_rows_within_server_cap(client, demo_url):
    """Server never returns more than 200 rows regardless of join size."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Network", "column": "VLAN"},
        "target": {"table": "Cluster", "column": "Name"},
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["rows"]) <= 200  # hard server-side cap via fetchmany(200)


def test_joinpath_run_respects_requested_max_rows(client, demo_url):
    """A small max_rows caps the returned rows and is echoed in row_cap (AP-6)."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Network", "column": "VLAN"},
        "target": {"table": "Cluster", "column": "Name"},
        "filters": [],
        "path_index": 0,
        "max_rows": 1,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["row_cap"] == 1
    assert len(data["rows"]) <= 1


def test_joinpath_run_all_rows_clamped_to_ceiling(client, demo_url):
    """max_rows=None ("Alle") clamps to the configured hard ceiling (AP-6)."""
    import config
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Network", "column": "VLAN"},
        "target": {"table": "Cluster", "column": "Name"},
        "filters": [],
        "path_index": 0,
        "max_rows": None,
    })
    assert resp.status_code == 200
    assert resp.get_json()["row_cap"] == config.MAX_RESULT_ROWS


def test_joinpath_run_unknown_column_returns_400(client, demo_url):
    """Unknown start column must be rejected with 400 before any SQL is run."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Network", "column": "NoSuchColumn"},
        "target": {"table": "Cluster", "column": "Name"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_ap3_orderby_offpath_excluded(client, inventory_url):
    """ORDER BY column from a table not on the path is silently excluded."""
    # Path Networks -> VirtualMachines -> VMwareCluster does NOT include OperatingSystems
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
        "order_by": [
            {"table": "OperatingSystems", "column": "OS_Family", "dir": "ASC"},
            {"table": "VirtualMachines", "column": "VMID", "dir": "DESC"},
        ],
    })
    assert resp.status_code == 200
    sql = resp.get_json()["paths"][0]["sql"]
    # OperatingSystems is off-path → excluded; VirtualMachines is on-path → included
    assert "OperatingSystems" not in sql or "ORDER BY" not in sql.split("OperatingSystems")[0]
    assert "VirtualMachines.VMID DESC" in sql
