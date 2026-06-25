"""Build an undirected NetworkX graph from a Schema's foreign keys.

Nodes are table names; each edge carries a "joins" tuple of
(left_table, left_col, right_table, right_col) describing how to join the
two tables. The graph is undirected because a join works in both directions.
Each edge also carries an "implied" flag: True only when the edge exists
solely because of implied (undeclared) foreign keys.
"""
import networkx as nx

from core.model import Schema


def _add_join_edge(g: nx.Graph, a: str, ac: str, b: str, bc: str, implied: bool) -> None:
    """Add or extend the join edge (a, b) with one join-column pair."""
    edge = (a, ac, b, bc)
    if g.has_edge(a, b):
        data = g[a][b]
        data["joins"] = data["joins"] + (edge,)
        if not implied:
            data["implied"] = False  # a declared join makes the edge declared
    else:
        g.add_edge(a, b, joins=(edge,), implied=implied)


def build_graph(schema: Schema, include_implied: bool = False) -> nx.Graph:
    """Build an undirected graph from a Schema.

    Args:
        schema: A Schema object containing tables and their foreign keys.
        include_implied: When True, also add edges for implied (undeclared)
            foreign keys detected by core.implied.find_implied_fks.

    Returns:
        An undirected NetworkX Graph where:
        - Nodes are table names (strings).
        - Edges connect tables with foreign keys.
        - Each edge has a "joins" attribute: a tuple of
          (left_table, left_col, right_table, right_col) tuples.
        - Each edge has an "implied" boolean attribute.
    """
    g = nx.Graph()
    for table in schema.tables:
        g.add_node(table.name)
    for table in schema.tables:
        for fk in table.foreign_keys:
            _add_join_edge(g, table.name, fk.column, fk.ref_table, fk.ref_column, False)
    if include_implied:
        from core.implied import find_implied_fks
        for ifk in find_implied_fks(schema):
            _add_join_edge(g, ifk.table, ifk.column, ifk.ref_table, ifk.ref_column, True)
    return g
