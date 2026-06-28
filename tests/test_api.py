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
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    save = client.post("/api/connections", json={
        "name": "prod", "db_type": "postgresql", "host": "h",
        "database": "cmdb", "user": "admin", "password": "SECRET"})
    assert save.status_code == 200
    conns = client.get("/api/connections").get_json()["connections"]
    saved = next(c for c in conns if c["name"] == "prod")
    assert saved["host"] == "h" and saved["database"] == "cmdb"
    assert "password" not in saved  # password is never persisted
    client.delete("/api/connections", json={"name": "prod"})


def test_mssql_connection_persists_encrypt_and_trust(client, tmp_path, monkeypatch):
    """AP-12: MSSQL Encrypt/TrustServerCertificate are saved with the connection."""
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    save = client.post("/api/connections", json={
        "name": "mssql_prod", "db_type": "mssql", "host": "h", "port": 1433,
        "database": "cmdb", "user": "sa", "password": "SECRET",
        "encrypt": "yes", "trust_server_certificate": "yes"})
    assert save.status_code == 200
    conns = client.get("/api/connections").get_json()["connections"]
    saved = next(c for c in conns if c["name"] == "mssql_prod")
    assert saved.get("encrypt") == "yes"
    assert saved.get("trust_server_certificate") == "yes"
    assert "password" not in saved
    client.delete("/api/connections", json={"name": "mssql_prod"})
    assert client.get("/api/connections").get_json()["connections"] == []


def test_connect_from_saved_sqlite_round_trip(client, demo_url, tmp_path, monkeypatch):
    # AP-10: the topbar picker connects directly from a saved (passwordless)
    # connection. Round-trip: save -> list -> connect using the saved entry
    # verbatim (exactly what connectSaved() posts to /api/connect).
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
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
        assert '"VirtualMachines"."VMID"' in p["sql"]
    # Start and target columns must still be present
    assert '"Networks"."VLAN"' in paths[0]["sql"]
    assert '"VMwareCluster"."ClusterID"' in paths[0]["sql"]


def test_joinpath_extra_select_off_path_now_woven(client, inventory_url):
    """AP-30: an extra-select from an off-axis lookup table is now woven into
    the join tree and its column appears in the SELECT (no silent drop)."""
    # Path Networks -> VirtualMachines -> VMwareCluster did NOT include OperatingSystems
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
        assert "OperatingSystems" in p["tables"]
        assert '"OperatingSystems"."OS_Family"' in p["sql"]


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
    assert '"VirtualMachines"."VMID" DESC' in sql
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
    assert '"VirtualMachines"."OSID" IS NULL' in sql
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


def test_joinpath_ap3_orderby_offpath_now_woven(client, inventory_url):
    """AP-30: an ORDER BY column from an off-axis table is now woven in and
    appears in the ORDER BY clause."""
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
    assert "OperatingSystems" in sql
    assert '"OperatingSystems"."OS_Family" ASC' in sql
    assert '"VirtualMachines"."VMID" DESC' in sql


def test_joinpath_n1_star_multi_lookup(client, inventory_url):
    """AP-30: one start (VirtualMachines) pulls attributes from three lookup
    tables in a single SELECT — all woven, no fan-out warning."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "VirtualMachines", "column": "VMID"},
        "target": {"table": "Networks", "column": "VLAN"},
        "extra_selects": [
            {"table": "OperatingSystems", "column": "OS_Family"},
            {"table": "VMwareCluster", "column": "ClusterName"},
        ],
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert '"Networks"."VLAN"' in p["sql"]
    assert '"OperatingSystems"."OS_Family"' in p["sql"]
    assert '"VMwareCluster"."ClusterName"' in p["sql"]


def test_joinpath_descending_branch_warns(client, inventory_url):
    """AP-30: a descending (1-N) step yields a non-blocking fan-out warning,
    but SQL is still generated."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VirtualMachines", "column": "VMID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert "SELECT" in p["sql"]            # generation still succeeds
    assert any("1-N" in w and "VirtualMachines" in w for w in p["warnings"])


def test_joinpath_steps_carry_direction(client, inventory_url):
    """Each join step exposes its direction (to_many) so the UI can label every
    edge N-1 / 1-N — not only flag the descending ones via warnings."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VirtualMachines", "column": "VMID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert p["steps"]
    # one entry per edge, identical order/orientation
    assert len(p["steps"]) == len(p["edges"])
    for s, e in zip(p["steps"], p["edges"]):
        assert [s["left"], s["right"]] == e
        assert isinstance(s["to_many"], bool)
    # descending into VirtualMachines → that step is to_many
    assert any(s["to_many"] and s["right"] == "VirtualMachines" for s in p["steps"])


def test_joinpath_sql_inline_has_runnable_literal(client, inventory_url):
    """The path carries a runnable `sql_inline` with the filter value substituted,
    while `sql` keeps the :p0 placeholder + params (execution path)."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [{"table": "VMwareCluster", "column": "ClusterID",
                     "op": "=", "value": "1"}],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert ":p0" in p["sql"] and p["params"] == {"p0": "1"}
    assert ":p0" not in p["sql_inline"]
    assert '"VMwareCluster"."ClusterID" = 1' in p["sql_inline"]


def test_joinpath_per_step_join_type(client, inventory_url):
    """AP-41: a per-step join type (LEFT) is rendered into the generated SQL."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
        "join_types": ["LEFT"],
    })
    assert resp.status_code == 200
    sql = resp.get_json()["paths"][0]["sql"]
    assert "LEFT JOIN" in sql


def test_orphan_check_returns_per_step_bool_flags(client, inventory_url):
    """AP-47: per join step, the endpoint reports which join types would actually
    change the result row count (count-based, path-context aware)."""
    resp = client.post("/api/orphan_check", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID"},
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    steps = resp.get_json()["steps"]
    assert isinstance(steps, list) and steps
    for s in steps:
        assert isinstance(s["left"], bool)
        assert isinstance(s["right"], bool)
        assert isinstance(s["full"], bool)


def test_orphan_check_text_mode_returns_empty(client):
    """Without a connection there is nothing to probe — empty, never an error."""
    resp = client.post("/api/orphan_check", json={"path_index": 0})
    assert resp.status_code == 200
    assert resp.get_json()["steps"] == []


def test_joinpath_ascending_star_has_no_warning(client, inventory_url):
    """AP-30: a pure N-1 star (all branches ascend) carries no fan-out warning."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "VirtualMachines", "column": "VMID"},
        "target": {"table": "Networks", "column": "VLAN"},
        "extra_selects": [
            {"table": "OperatingSystems", "column": "OS_Family"},
            {"table": "VMwareCluster", "column": "ClusterName"},
        ],
        "filters": [],
    })
    assert resp.status_code == 200
    assert resp.get_json()["paths"][0]["warnings"] == []


# ===== AP-25: /api/analyze =====

def test_analyze_text_mode_no_connection(client):
    resp = client.post("/api/analyze", json={
        "sql": "UPDATE Host SET Hostname='x'",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["statement_type"] == "UPDATE"
    assert data["tables_written"] == ["Host"]
    codes = {w["code"] for w in data["warnings"]}
    assert {"WRITE_STATEMENT", "NO_WHERE"} <= codes
    # text mode: no schema-dependent warnings
    assert "UNKNOWN_TABLE" not in codes


def test_analyze_with_connection_flags_unknown_table(client, inventory_url):
    resp = client.post("/api/analyze", json={
        "sql": "SELECT * FROM NoSuchTable",
        "connection_url": inventory_url,
    })
    assert resp.status_code == 200
    codes = {w["code"] for w in resp.get_json()["warnings"]}
    assert "UNKNOWN_TABLE" in codes


def test_analyze_parse_error_returns_200_with_error(client):
    resp = client.post("/api/analyze", json={"sql": "NOT SQL @@@"})
    assert resp.status_code == 200
    assert resp.get_json()["parse_error"] is not None


def test_analyze_bad_connection_returns_400(client):
    resp = client.post("/api/analyze", json={
        "sql": "SELECT 1",
        "connection_url": "sqlite:////nonexistent_dir_xyz/zzz.db",
    })
    # a connection that cannot reflect → 400 (reflection raises ConnectionError)
    assert resp.status_code == 400


def test_analyze_returns_optimization_suggestions(client):
    resp = client.post("/api/analyze",
                       json={"sql": "SELECT DISTINCT a FROM t GROUP BY a"})
    assert resp.status_code == 200
    data = resp.get_json()
    codes = {s["code"] for s in data["suggestions"]}
    assert "DISTINCT_WITH_GROUP_BY" in codes


# ===== AP-45: /api/joinpath/run columns_meta =====

def test_joinpath_run_returns_columns_meta(client, demo_url):
    """AP-45: the result carries a per-column (table, column) map in selection
    order, so a result <th> can be traced back to its source column even when
    two joined tables share a column name."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Network", "column": "VLAN"},
        "target": {"table": "Cluster", "column": "Name"},
        "extra_selects": [{"table": "Datacenter", "column": "Name"}],
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    meta = resp.get_json()["columns_meta"]
    # one entry per output column, same order as `columns`
    assert len(meta) == len(resp.get_json()["columns"])
    # start, target, then the extra select — in that order
    assert meta[0] == {"table": "Network", "column": "VLAN"}
    assert meta[1] == {"table": "Cluster", "column": "Name"}
    assert meta[2] == {"table": "Datacenter", "column": "Name"}


# ===== AP-45: /api/distinct =====

def test_distinct_returns_sorted_unique_values(client, demo_url):
    """AP-45: /api/distinct returns the distinct values of one column, sorted,
    for the filter-value dropdown."""
    resp = client.post("/api/distinct", json={
        "connection_url": demo_url,
        "table": "Cluster",
        "column": "Name",
    })
    assert resp.status_code == 200
    values = resp.get_json()["values"]
    assert isinstance(values, list)
    assert len(values) >= 1
    assert len(values) == len(set(values))          # unique
    assert values == sorted(values)                 # sorted ascending


def test_distinct_capped(client, demo_url):
    """The result is capped so a huge column can never flood the dropdown."""
    import config
    resp = client.post("/api/distinct", json={
        "connection_url": demo_url,
        "table": "Network",
        "column": "NetworkID",
    })
    assert resp.status_code == 200
    assert len(resp.get_json()["values"]) <= config.DISTINCT_LIMIT


def test_distinct_unknown_column_best_effort_empty(client, demo_url):
    """An unknown column is a best-effort no-op (empty list, 200) — like
    /api/orphan_check, it never blocks the form."""
    resp = client.post("/api/distinct", json={
        "connection_url": demo_url,
        "table": "Cluster",
        "column": "NoSuchColumn",
    })
    assert resp.status_code == 200
    assert resp.get_json()["values"] == []


def test_distinct_no_connection_best_effort_empty(client):
    """No connection URL → empty list, 200 (best-effort hint)."""
    resp = client.post("/api/distinct", json={"table": "Cluster", "column": "Name"})
    assert resp.status_code == 200
    assert resp.get_json()["values"] == []


def test_one_to_one_path_has_no_fanout_warning(client, onetoone_url):
    """A 1-1 join (UNIQUE FK) must not raise the 1-N fan-out warning."""
    resp = client.post("/api/joinpath", json={
        "connection_url": onetoone_url,
        "start": {"table": "Person", "column": "PersonID"},
        "target": {"table": "Passport", "column": "PassportID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert all("1-N" not in w for w in p["warnings"])


def test_one_to_many_path_still_warns(client, onetoone_url):
    """A 1-N join (non-unique FK) still raises the fan-out warning."""
    resp = client.post("/api/joinpath", json={
        "connection_url": onetoone_url,
        "start": {"table": "Person", "column": "PersonID"},
        "target": {"table": "Orders", "column": "OrderID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert any("1-N" in w and "Orders" in w for w in p["warnings"])


def test_index_unique_path_has_no_fanout_warning(client, uniqueindex_url):
    """A 1-1 join whose uniqueness comes from a UNIQUE INDEX must not warn 1-N."""
    resp = client.post("/api/joinpath", json={
        "connection_url": uniqueindex_url,
        "start": {"table": "Parent", "column": "ParentID"},
        "target": {"table": "Profile", "column": "ProfileID"},
        "filters": [],
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert all("1-N" not in w for w in p["warnings"])


# ===== AP-52: /api/schemas + schema param on reflect endpoints =====

def test_schemas_endpoint_lists_main(client, inventory_url):
    resp = client.post("/api/schemas", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    assert "main" in resp.get_json()["schemas"]


def test_data_endpoint_with_schema_returns_rows(client, inventory_url):
    resp = client.post("/api/data", json={
        "connection_url": inventory_url, "object": "VirtualMachines",
        "schema": "main",
    })
    assert resp.status_code == 200
    assert "columns" in resp.get_json()


def test_joinpath_with_schema_qualifies_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VirtualMachines", "column": "VMID"},
        "filters": [], "schema": "main",
    })
    assert resp.status_code == 200
    p = resp.get_json()["paths"][0]
    assert '"main"."Networks"' in p["sql"]


def test_joinpath_run_with_schema_executes(client, inventory_url):
    resp = client.post("/api/joinpath/run", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VirtualMachines", "column": "VMID"},
        "filters": [], "schema": "main", "path_index": 0,
    })
    assert resp.status_code == 200
    assert "columns" in resp.get_json()


def test_schema_endpoint_serializes_comments(client, monkeypatch):
    from core.model import Column, Table, Schema
    import web.routes as routes

    class _FakeLoader:
        def __init__(self, url):
            pass

        def load(self, schema=None):
            cols = (Column("a", "INT", comment="Spalten-Notiz"),)
            return Schema((Table("t", cols, (), comment="Tabellen-Notiz"),))

    monkeypatch.setattr(routes, "SqlAlchemyLoader", _FakeLoader)
    data = client.post("/api/schema", json={"connection_url": "fake://"}).get_json()
    table = data["tables"][0]
    assert table["comment"] == "Tabellen-Notiz"
    assert table["columns"][0]["comment"] == "Spalten-Notiz"


def test_schema_endpoint_comment_key_present_for_sqlite(client, inventory_url):
    # SQLite: keine Kommentare → Schlüssel vorhanden, Wert leer.
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    t = data["tables"][0]
    assert t["comment"] == ""
    assert t["columns"]  # nicht-leer: all() darf nicht vacuous bestehen
    assert all(c["comment"] == "" for c in t["columns"])


def test_oracle_connection_persists_service_name(client, tmp_path, monkeypatch):
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    save = client.post("/api/connections", json={
        "name": "Ora", "db_type": "oracle", "host": "h", "port": 1521,
        "service_name": "XEPDB1", "user": "u",
    })
    assert save.status_code == 200
    got = client.get("/api/connections").get_json()["connections"]
    ora = next(c for c in got if c["name"] == "Ora")
    assert ora["db_type"] == "oracle"
    assert ora["service_name"] == "XEPDB1"
    assert "password" not in ora


# ===== Tier-3: aggregate / GROUP BY via route layer =====

def test_joinpath_aggregate_emits_group_by(client, inventory_url):
    """An agg on the target column produces FUNC(col) + GROUP BY on the rest."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "filters": [],
    })
    assert resp.status_code == 200
    sql = resp.get_json()["paths"][0]["sql"]
    assert 'COUNT("VMwareCluster"."ClusterID")' in sql
    assert 'GROUP BY "Networks"."VLAN"' in sql


def test_joinpath_unknown_aggregate_returns_400(client, inventory_url):
    """An unsupported aggregate is rejected with 400 (ValueError from generator)."""
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "MEDIAN"},
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_run_executes_grouped_aggregate(client, demo_url):
    """Read-only run path executes a grouped COUNT and returns grouped rows.

    Host 1-N VirtualMachine (VM.HostID -> Host): count VMs per host.
    """
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "VirtualMachine", "column": "VMID", "agg": "COUNT"},
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "GROUP BY" in data["sql"]
    assert isinstance(data["rows"], list) and len(data["rows"]) >= 1


# ===== Tier-3: order_by agg + having via route layer =====

def test_joinpath_order_by_aggregate_in_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "order_by": [{"table": "VMwareCluster", "column": "ClusterID", "dir": "DESC", "agg": "COUNT"}],
        "filters": [],
    })
    assert resp.status_code == 200
    assert 'ORDER BY COUNT("VMwareCluster"."ClusterID") DESC' in resp.get_json()["paths"][0]["sql"]


def test_joinpath_having_emits_clause(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "having": [{"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT", "op": ">", "value": 1}],
        "filters": [],
    })
    assert resp.status_code == 200
    sql = resp.get_json()["paths"][0]["sql"]
    assert 'HAVING COUNT("VMwareCluster"."ClusterID") > :h0' in sql


def test_joinpath_having_unknown_op_returns_400(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT"},
        "having": [{"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT", "op": "LIKE", "value": "x"}],
        "filters": [],
    })
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_joinpath_having_table_woven_into_path(client, demo_url):
    """A HAVING on a table off the start/target path is woven in (required_tables)."""
    resp = client.post("/api/joinpath", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "Host", "column": "HostID"},
        "having": [{"table": "VirtualMachine", "column": "VMID", "agg": "COUNT", "op": ">=", "value": 1}],
        "filters": [],
    })
    assert resp.status_code == 200
    paths = resp.get_json()["paths"]
    assert paths
    for p in paths:
        assert "VirtualMachine" in p["tables"]
        assert 'HAVING COUNT("VirtualMachine"."VMID") >=' in p["sql"]


def test_joinpath_run_executes_having(client, demo_url):
    """Read-only run executes a grouped query with HAVING and returns grouped rows."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "VirtualMachine", "column": "VMID", "agg": "COUNT"},
        "having": [{"table": "VirtualMachine", "column": "VMID", "agg": "COUNT", "op": ">=", "value": 1}],
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "HAVING" in data["sql"]
    assert isinstance(data["rows"], list) and len(data["rows"]) >= 1


# ===== COUNT(*) + COUNT(DISTINCT) via route layer =====

def test_joinpath_count_distinct_in_sql(client, inventory_url):
    resp = client.post("/api/joinpath", json={
        "connection_url": inventory_url,
        "start": {"table": "Networks", "column": "VLAN"},
        "target": {"table": "VMwareCluster", "column": "ClusterID", "agg": "COUNT DISTINCT"},
        "filters": [],
    })
    assert resp.status_code == 200
    assert 'COUNT(DISTINCT "VMwareCluster"."ClusterID")' in resp.get_json()["paths"][0]["sql"]


def test_joinpath_run_executes_count_star(client, demo_url):
    """COUNT(*) per host over the joined VirtualMachine rows, read-only run."""
    resp = client.post("/api/joinpath/run", json={
        "connection_url": demo_url,
        "start": {"table": "Host", "column": "Hostname"},
        "target": {"table": "VirtualMachine", "column": "VMID", "agg": "COUNT*"},
        "having": [{"table": "VirtualMachine", "column": "VMID", "agg": "COUNT*", "op": ">=", "value": 1}],
        "filters": [],
        "path_index": 0,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "COUNT(*)" in data["sql"]
    assert "HAVING COUNT(*) >=" in data["sql"]
    assert isinstance(data["rows"], list) and len(data["rows"]) >= 1


# ===== AP-54: Cross-Schema-FK-Diagnose =====

def test_schema_includes_cross_schema_fks_key(client, inventory_url):
    resp = client.post("/api/schema", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "cross_schema_fks" in data
    assert data["cross_schema_fks"] == []   # SQLite has no cross-schema FKs


def test_schema_endpoint_returns_implied_fks(client, inventory_nofk_url):
    data = client.post("/api/schema", json={"connection_url": inventory_nofk_url}).get_json()
    assert "implied_fks" in data
    entry = next(e for e in data["implied_fks"]
                 if e["from_table"] == "VirtualMachines" and e["column"] == "OSID")
    assert entry["to_table"] == "OperatingSystems"
    assert entry["to_column"] == "OSID"
    assert entry["confidence"] == "hoch"
    assert entry["reason"]
