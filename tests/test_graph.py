from core.graph import build_graph
from core.loaders.sqlalchemy_loader import SqlAlchemyLoader


def test_graph_nodes_are_tables(inventory_url):
    g = build_graph(SqlAlchemyLoader(inventory_url).load())
    assert set(g.nodes) == {
        "OperatingSystems", "VMwareCluster", "Networks", "VirtualMachines",
    }


def test_graph_has_fk_edges_with_join_columns(inventory_url):
    g = build_graph(SqlAlchemyLoader(inventory_url).load())
    assert g.has_edge("VirtualMachines", "Networks")
    joins = g["VirtualMachines"]["Networks"]["joins"]
    # normalize to a set of frozensets so edge direction doesn't matter
    pairs = {frozenset(((lt, lc), (rt, rc))) for (lt, lc, rt, rc) in joins}
    assert frozenset((("VirtualMachines", "NetworkID"), ("Networks", "NetworkID"))) in pairs


def test_isolated_table_is_still_a_node(inventory_url):
    # VMwareCluster has no outgoing FK but is referenced — must still be a node
    g = build_graph(SqlAlchemyLoader(inventory_url).load())
    assert "VMwareCluster" in g.nodes
