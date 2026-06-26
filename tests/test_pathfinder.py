import pytest
from core.graph import build_graph
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.pathfinder import find_paths, NoPathError
import config


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


def test_required_table_is_woven_in(graph):
    # Start/target on the Networks<->Cluster axis, filter forces OperatingSystems in
    paths = find_paths(graph, "Networks", "VMwareCluster",
                       required_tables=("OperatingSystems",))
    assert "OperatingSystems" in paths[0].tables


def test_no_path_raises():
    import networkx as nx
    g = nx.Graph()
    g.add_node("A")
    g.add_node("B")
    with pytest.raises(NoPathError):
        find_paths(g, "A", "B")


def test_required_table_weave_has_no_duplicate_tables(graph):
    paths = find_paths(graph, "Networks", "VMwareCluster",
                       required_tables=("OperatingSystems",))
    p = paths[0]
    # every table appears exactly once (valid for single-alias SQL joins)
    assert len(p.tables) == len(set(p.tables))
    # each join step introduces a table not seen before its step
    seen = {p.tables[0]}
    for step in p.steps:
        assert step.left_table in seen          # left side already joined
        assert step.right_table not in seen      # right side is the new table
        seen.add(step.right_table)
    assert "OperatingSystems" in p.tables


def test_enumeration_cap_respected(graph):
    # The enumeration cap must not be exceeded and the shortest path must still be first.
    paths = find_paths(graph, "Networks", "VMwareCluster")
    assert len(paths) <= config.MAX_PATH_ENUMERATION
    # Shortest path from the test schema is the two-hop Networks -> VirtualMachines -> VMwareCluster
    assert paths[0].tables == ("Networks", "VirtualMachines", "VMwareCluster")


def test_step_to_one_when_ascending(graph):
    # VirtualMachines holds the FK to Networks → VM->Networks is child->parent (N-1)
    paths = find_paths(graph, "VirtualMachines", "Networks")
    step = paths[0].steps[0]
    assert step.left_table == "VirtualMachines" and step.right_table == "Networks"
    assert step.to_many is False


def test_step_to_many_when_descending(graph):
    # Networks->VirtualMachines descends (one Network, many VMs) → fan-out
    paths = find_paths(graph, "Networks", "VirtualMachines")
    step = paths[0].steps[0]
    assert step.left_table == "Networks" and step.right_table == "VirtualMachines"
    assert step.to_many is True


def test_required_table_unreachable_raises(graph):
    # OperatingSystems is reachable; an isolated bogus table is not.
    import networkx as nx
    g = nx.Graph(graph)
    g.add_node("Orphan")
    with pytest.raises(NoPathError):
        find_paths(g, "Networks", "VMwareCluster", required_tables=("Orphan",))
