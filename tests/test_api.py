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


def test_schema_empty_connection_returns_400(client):
    resp = client.post("/api/schema", json={"connection_url": ""})
    assert resp.status_code == 400
    assert "error" in resp.get_json()
