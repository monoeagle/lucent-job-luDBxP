import pytest
from web import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_schema_endpoint_returns_tables(client, inventory_url):
    resp = client.post("/api/schema", json={"connection_url": inventory_url})
    assert resp.status_code == 200
    names = {t["name"] for t in resp.get_json()["tables"]}
    assert "VirtualMachines" in names


def test_schema_returns_column_details_fks_and_views(client, inventory_url):
    data = client.post("/api/schema", json={"connection_url": inventory_url}).get_json()
    vm = next(t for t in data["tables"] if t["name"] == "VirtualMachines")
    vmid = next(c for c in vm["columns"] if c["name"] == "VMID")
    assert vmid["pk"] is True and vmid["type"]
    assert any(fk["ref_table"] == "Networks" for fk in vm["foreign_keys"])
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
