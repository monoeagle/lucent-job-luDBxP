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


def _to_join_path(graph: nx.Graph, node_seq: list[str]) -> JoinPath:
    """Convert an ordered node sequence into a JoinPath with typed steps.

    Args:
        graph: The FK graph.
        node_seq: Ordered list of table names forming the path.  All
            consecutive pairs must share a direct edge in the graph.

    Returns:
        A JoinPath dataclass instance.
    """
    steps = tuple(
        _join_step(graph, node_seq[i], node_seq[i + 1])
        for i in range(len(node_seq) - 1)
    )
    return JoinPath(tuple(node_seq), steps)


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
    woven in via the shortest connecting sub-path from the nearest node
    already on the path.  When the nearest anchor is not the current tail of
    the sequence, the implementation backtracks from the tail to the anchor
    first so that all consecutive pairs in the final sequence share a direct
    edge in the graph.

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
        seq = list(node_seq)

        # Weave in each filter table not already present on the path.
        for ftable in filter_tables:
            if ftable in seq:
                continue

            # Find the nearest node in seq that can reach ftable (shortest
            # connecting path, deterministic tie-break via lexicographic order).
            best: list[str] | None = None
            for node in seq:
                try:
                    conn = nx.shortest_path(graph, node, ftable)
                except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                    raise NoPathError(
                        f"Filter table {ftable} is not connected"
                    ) from exc
                if best is None or (len(conn), conn) < (len(best), best):
                    best = conn

            assert best is not None  # loop over seq guarantees at least one try
            anchor = best[0]

            # If the anchor is not the current tail we must first backtrack
            # from the tail to the anchor so that every consecutive pair in
            # the sequence has a direct edge in the graph.
            if seq[-1] != anchor:
                try:
                    return_path = nx.shortest_path(graph, seq[-1], anchor)
                except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                    raise NoPathError(
                        f"Cannot return from {seq[-1]} to anchor {anchor}"
                    ) from exc
                # Append return path nodes (duplicates allowed — they are
                # needed to keep consecutive-pair edges intact).
                seq.extend(return_path[1:])

            # Now the tail is the anchor; append the branch to ftable.
            seq.extend(best[1:])

        results.append(_to_join_path(graph, seq))

    return results
