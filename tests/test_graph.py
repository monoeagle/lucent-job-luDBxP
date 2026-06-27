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
    pairs = {
        frozenset(((j.table_a, lc), (j.table_b, rc)))
        for j in joins for (lc, rc) in j.pairs
    }
    assert frozenset((("VirtualMachines", "NetworkID"), ("Networks", "NetworkID"))) in pairs


def test_isolated_table_is_still_a_node(inventory_url):
    # VMwareCluster has no outgoing FK but is referenced — must still be a node
    g = build_graph(SqlAlchemyLoader(inventory_url).load())
    assert "VMwareCluster" in g.nodes


def _edge_with_holder(g, holder, other):
    """The JoinEdge on (holder, other) whose table_a is the FK holder."""
    joins = g[holder][other]["joins"]
    return next(j for j in joins if j.table_a == holder)


def test_join_edge_fk_unique_for_one_to_one(onetoone_url):
    g = build_graph(SqlAlchemyLoader(onetoone_url).load())
    # Passport holds a UNIQUE FK to Person → 1-1
    assert _edge_with_holder(g, "Passport", "Person").fk_unique is True


def test_join_edge_fk_not_unique_for_one_to_many(onetoone_url):
    g = build_graph(SqlAlchemyLoader(onetoone_url).load())
    # Orders holds a non-unique FK to Person → 1-N
    assert _edge_with_holder(g, "Orders", "Person").fk_unique is False
