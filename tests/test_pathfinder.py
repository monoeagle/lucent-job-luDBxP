import pytest
from core.graph import build_graph
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.pathfinder import find_paths, NoPathError


@pytest.fixture
def graph(inventory_url):
    return build_graph(SqlAlchemyLoader(inventory_url).load())


def test_direct_path_networks_to_vm(graph):
    paths = find_paths(graph, "Networks", "VirtualMachines")
    assert paths[0].tables == ("Networks", "VirtualMachines")
    step = paths[0].steps[0]
    assert {step.left_table, step.right_table} == {"Networks", "VirtualMachines"}


def test_two_hop_networks_to_cluster(graph):
    # Networks -> VirtualMachines -> VMwareCluster
    paths = find_paths(graph, "Networks", "VMwareCluster")
    assert paths[0].tables == ("Networks", "VirtualMachines", "VMwareCluster")


def test_determinism(graph):
    a = find_paths(graph, "Networks", "VMwareCluster")
    b = find_paths(graph, "Networks", "VMwareCluster")
    assert [p.tables for p in a] == [p.tables for p in b]


def test_filter_table_is_woven_in(graph):
    # Start/target on the Networks<->Cluster axis, filter forces OperatingSystems in
    paths = find_paths(graph, "Networks", "VMwareCluster",
                       filter_tables=("OperatingSystems",))
    assert "OperatingSystems" in paths[0].tables


def test_no_path_raises():
    import networkx as nx
    g = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    with pytest.raises(NoPathError):
        find_paths(g, "A", "B")
