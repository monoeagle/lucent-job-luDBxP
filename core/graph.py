"""Build an undirected NetworkX graph from a Schema's foreign keys.

Nodes are table names; each edge carries a "joins" tuple of
(left_table, left_col, right_table, right_col) describing how to join the
two tables. The graph is undirected because a join works in both directions.
"""
import networkx as nx

from core.model import Schema


def build_graph(schema: Schema) -> nx.Graph:
    """Build an undirected graph from a Schema.

    Args:
        schema: A Schema object containing tables and their foreign keys.

    Returns:
        An undirected NetworkX Graph where:
        - Nodes are table names (strings).
        - Edges connect tables with foreign keys.
        - Each edge has a "joins" attribute: a tuple of
          (left_table, left_col, right_table, right_col) tuples.
    """
    g = nx.Graph()
    for table in schema.tables:
        g.add_node(table.name)
    for table in schema.tables:
        for fk in table.foreign_keys:
            edge = (table.name, fk.column, fk.ref_table, fk.ref_column)
            if g.has_edge(table.name, fk.ref_table):
                existing = g[table.name][fk.ref_table]["joins"]
                g[table.name][fk.ref_table]["joins"] = existing + (edge,)
            else:
                g.add_edge(table.name, fk.ref_table, joins=(edge,))
    return g
