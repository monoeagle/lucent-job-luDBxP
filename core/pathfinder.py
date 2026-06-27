"""Find join paths between two tables, weaving in required filter tables.

Shortest-first with a deterministic tie-break (lexicographic table sequence)
so identical input always yields identical SQL. Returns up to k candidates.
"""
import itertools
from dataclasses import dataclass

import networkx as nx

import config


class NoPathError(Exception):
    """Raised when no join path connects the requested tables."""


@dataclass(frozen=True)
class JoinStep:
    left_table: str
    right_table: str
    # One (left_col, right_col) pair per key column; >1 pair = composite FK,
    # all combined with AND in the emitted JOIN ... ON clause.
    column_pairs: tuple[tuple[str, str], ...]
    # True when this step descends a foreign key (left=parent -> right=child,
    # i.e. right holds the FK): a one-to-many edge that can multiply rows.
    to_many: bool = False


@dataclass(frozen=True)
class JoinPath:
    tables: tuple[str, ...]
    steps: tuple[JoinStep, ...]


def _oriented_pairs(option, a: str) -> tuple[tuple[str, str], ...]:
    """Return option.pairs oriented so each pair reads (a_column, other_column)."""
    if option.table_a == a:
        return option.pairs
    return tuple((b_col, a_col) for a_col, b_col in option.pairs)


def _join_step(graph: nx.Graph, a: str, b: str) -> JoinStep:
    """Pick a join option for edge (a, b), oriented a -> b deterministically.

    When several foreign keys connect a and b (alternative routes), the
    lexicographically smallest oriented pair-set is chosen so identical input
    always yields identical SQL. The chosen option may be single-column or
    composite; all its column pairs are carried into the JoinStep and later
    rendered as ``ON p1 AND p2 …``.

    Args:
        graph: The FK graph produced by build_graph.
        a: Source table name.
        b: Target table name.

    Returns:
        A JoinStep with left_table == a, carrying all column pairs of the
        chosen foreign key.
    """
    options = graph[a][b]["joins"]
    # Deterministic choice: the option whose a-oriented pairs sort smallest.
    chosen = min(options, key=lambda o: _oriented_pairs(o, a))
    pairs = _oriented_pairs(chosen, a)
    # The chosen FK is held by chosen.table_a (the child side). Stepping a -> b
    # descends (one-to-many) when b is that FK holder — unless the FK columns are
    # themselves unique (chosen.fk_unique), which makes the step one-to-one.
    to_many = (chosen.table_a == b) and not chosen.fk_unique
    return JoinStep(a, b, pairs, to_many)


def find_paths(
    graph,
    start_table,
    target_table,
    required_tables=(),
    k=config.MAX_JOIN_PATHS,
):
    """Find up to k join paths from start_table to target_table.

    Paths are returned shortest-first.  Ties are broken deterministically by
    lexicographic node sequence so that identical inputs always produce
    identical output.  Required tables not already on a candidate path are
    woven in as branches of a join tree: each missing required table is attached
    to the nearest already-included node via the shortest connecting sub-path,
    adding only new nodes.  No table ever appears more than once in the
    resulting JoinPath, making every step safe to emit as a SQL JOIN clause.

    At most MAX_PATH_ENUMERATION shortest paths are enumerated from the
    NetworkX generator before k-selection; this bounds memory and runtime on
    schemas with many alternative routes.

    Args:
        graph: A NetworkX Graph produced by build_graph().
        start_table: Name of the starting table.
        target_table: Name of the target table.
        required_tables: Optional sequence of table names that must appear in
            every returned path (filter, selected-column and order-by tables),
            woven in as branches of a join tree.
        k: Maximum number of paths to return.

    Returns:
        A list of JoinPath instances, shortest-first.

    Raises:
        NoPathError: If start_table, target_table, or any required_table is
            unknown or not reachable.
    """
    if start_table not in graph or target_table not in graph:
        raise NoPathError(f"Unknown table: {start_table} or {target_table}")

    # Collect at most MAX_PATH_ENUMERATION shortest simple paths, then sort for determinism.
    try:
        raw = list(itertools.islice(
            nx.shortest_simple_paths(graph, start_table, target_table),
            config.MAX_PATH_ENUMERATION,
        ))
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise NoPathError(
            f"No join path between {start_table} and {target_table}"
        ) from exc

    # Sort by length first, then lexicographic node sequence for a fully
    # deterministic order independent of NetworkX's internal traversal order.
    raw.sort(key=lambda seq: (len(seq), seq))
    candidates = raw[:k]

    results = []
    for node_seq in candidates:
        included = list(node_seq)          # simple path: already unique, ordered
        included_set = set(node_seq)
        steps = [
            _join_step(graph, node_seq[i], node_seq[i + 1])
            for i in range(len(node_seq) - 1)
        ]

        for ftable in required_tables:
            if ftable in included_set:
                continue
            # Find the nearest included node that reaches ftable
            # (deterministic tie-break via lexicographic path).
            best: list[str] | None = None
            for node in included:
                try:
                    # Deterministic: among all shortest paths from this node to
                    # ftable, take the lexicographically smallest.
                    conn = min(nx.all_shortest_paths(graph, node, ftable))
                except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                    raise NoPathError(
                        f"Required table {ftable} is not connected"
                    ) from exc
                if best is None or (len(conn), conn) < (len(best), best):
                    best = conn
            # best = [anchor, ..., ftable]; anchor is already included.
            # Add each new node along the branch, joined to its predecessor.
            for i in range(len(best) - 1):
                a, b = best[i], best[i + 1]
                if b not in included_set:
                    steps.append(_join_step(graph, a, b))
                    included.append(b)
                    included_set.add(b)

        results.append(JoinPath(tuple(included), tuple(steps)))

    return results
