"""Build an undirected NetworkX graph from a Schema's foreign keys.

Nodes are table names; each edge carries a "joins" tuple of JoinEdge objects.
A JoinEdge describes one foreign key between two tables as its set of
(column_on_a, column_on_b) pairs: a single-column FK has one pair, a composite
FK has several (all joined with AND). Two *separate* FKs between the same two
tables produce two JoinEdge entries (alternative join routes), never merged.
The graph is undirected because a join works in both directions. Each edge also
carries an "implied" flag: True only when the edge exists solely because of
implied (undeclared) foreign keys.
"""
from dataclasses import dataclass

import networkx as nx

from core.model import Schema


@dataclass(frozen=True)
class JoinEdge:
    """One foreign key between two tables, as oriented column pairs.

    ``pairs`` holds ``(column_on_table_a, column_on_table_b)`` tuples — one for
    a single-column FK, several for a composite FK (all combined with AND).
    ``fk_unique`` is True when ``table_a``'s FK columns are collectively unique
    (the relationship is one-to-one, not one-to-many).
    """
    table_a: str
    table_b: str
    pairs: tuple[tuple[str, str], ...]
    fk_unique: bool = False


def _columns_unique(table, columns) -> bool:
    """True if ``columns`` on ``table`` are collectively unique: some unique set
    (a UNIQUE constraint or the primary key) is a subset of ``columns``."""
    target = set(columns)
    if not target:
        return False
    candidates = list(table.unique_constraints)
    if table.primary_key:
        candidates.append(table.primary_key)
    return any(set(u) <= target for u in candidates if u)


def _add_join_edge(g: nx.Graph, a: str, b: str,
                   pairs: tuple[tuple[str, str], ...], implied: bool,
                   fk_unique: bool = False) -> None:
    """Add or extend the (a, b) edge with one join option (one foreign key)."""
    option = JoinEdge(a, b, pairs, fk_unique)
    if g.has_edge(a, b):
        data = g[a][b]
        data["joins"] = data["joins"] + (option,)
        if not implied:
            data["implied"] = False  # a declared join makes the edge declared
    else:
        g.add_edge(a, b, joins=(option,), implied=implied)


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
        - Each edge has a "joins" attribute: a tuple of JoinEdge objects, one
          per foreign key (single-column or composite).
        - Each edge has an "implied" boolean attribute.
    """
    g = nx.Graph()
    for table in schema.tables:
        g.add_node(table.name)
    for table in schema.tables:
        for fk in table.foreign_keys:
            fk_unique = _columns_unique(table, fk.columns)
            _add_join_edge(g, table.name, fk.ref_table, fk.column_pairs,
                           False, fk_unique)
    if include_implied:
        from core.implied import find_implied_fks
        for ifk in find_implied_fks(schema):
            _add_join_edge(g, ifk.table, ifk.ref_table,
                           ((ifk.column, ifk.ref_column),), True)
    return g
