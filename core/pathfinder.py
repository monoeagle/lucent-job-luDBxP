"""Find join paths between two tables, weaving in required filter tables.

Shortest-first with a deterministic tie-break (lexicographic table sequence)
so identical input always yields identical SQL. Returns up to k candidates.
"""
from dataclasses import dataclass

import networkx as nx

import config


class NoPathError(Exception):
    """Raised when no join path connects the requested tables."""


@dataclass(frozen=True)
class JoinStep:
    left_table: str
    left_col: str
    right_table: str
    right_col: str


@dataclass(frozen=True)
class JoinPath:
    tables: tuple[str, ...]
    steps: tuple[JoinStep, ...]


def _join_step(graph: nx.Graph, a: str, b: str) -> JoinStep:
    """Pick the first join pair for edge (a,b), oriented a -> b deterministically.

    Args:
        graph: The FK graph produced by build_graph.
        a: Source table name.
        b: Target table name.

    Returns:
        A JoinStep with left_table == a.
    """
    joins = graph[a][b]["joins"]
    # Deterministic: sort the candidate join tuples, take the first.
    lt, lc, rt, rc = sorted(joins)[0]
    if lt == a:
        return JoinStep(lt, lc, rt, rc)
    return JoinStep(rt, rc, lt, lc)


def find_paths(
    graph,
    start_table,
    target_table,
    filter_tables=(),
    k=config.MAX_JOIN_PATHS,
):
    """Find up to k join paths from start_table to target_table.

    Paths are returned shortest-first.  Ties are broken deterministically by
    lexicographic node sequence so that identical inputs always produce
    identical output.  Filter tables not already on a candidate path are
    woven in as branches of a join tree: each missing filter table is attached
    to the nearest already-included node via the shortest connecting sub-path,
    adding only new nodes.  No table ever appears more than once in the
    resulting JoinPath, making every step safe to emit as a SQL JOIN clause.

    Args:
        graph: A NetworkX Graph produced by build_graph().
        start_table: Name of the starting table.
        target_table: Name of the target table.
        filter_tables: Optional sequence of table names that must appear in
            every returned path.
        k: Maximum number of paths to return.

    Returns:
        A list of JoinPath instances, shortest-first.

    Raises:
        NoPathError: If start_table, target_table, or any filter_table is
            unknown or not reachable.
    """
    if start_table not in graph or target_table not in graph:
        raise NoPathError(f"Unknown table: {start_table} or {target_table}")

    # Collect k shortest simple paths, then sort for determinism.
    try:
        raw = list(nx.shortest_simple_paths(graph, start_table, target_table))
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

        for ftable in filter_tables:
            if ftable in included_set:
                continue
            # Find the nearest included node that reaches ftable
            # (deterministic tie-break via lexicographic path).
            best: list[str] | None = None
            for node in included:
                try:
                    conn = nx.shortest_path(graph, node, ftable)
                except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                    raise NoPathError(
                        f"Filter table {ftable} is not connected"
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
