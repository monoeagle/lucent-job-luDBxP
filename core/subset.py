"""Schema-level database subsetting (AP-56a): the referential footprint of an
entity. Pure schema logic — executes nothing. The live data-driven walk is AP-56b.

Closure rule (Jailer-style "down-then-up"): from the start table, collect
dependents downward via reverse foreign keys (children), then collect the
lookups those rows need upward via foreign keys (parents) WITHOUT descending
again — this keeps the subset referentially complete without exploding.
"""
import heapq
import numbers
from collections import deque
from dataclasses import dataclass

from core.model import Schema
from core.sqlgen import Dialect, SQLITE


@dataclass(frozen=True)
class SubsetEdge:
    via_table: str                          # predecessor in the derivation tree
    pairs: tuple[tuple[str, str], ...]      # (child_local_col, parent_ref_col)
    child_table: str                        # which endpoint holds the FK (child side)
    kind: str                               # "child" | "parent" | "root"


@dataclass(frozen=True)
class SubsetTable:
    name: str
    edge: "SubsetEdge | None"               # None only for the root table
    depth: int


@dataclass(frozen=True)
class SubsetResult:
    start: str
    tables: tuple[SubsetTable, ...]         # topologically sorted (parents first)
    truncated: bool


def _adjacency(schema: Schema, include_implied: bool):
    """Directed FK adjacency. Returns (parents_of, children_of), each
    table -> list of (other_table, pairs) where pairs are (child_local, parent_ref)."""
    parents_of: dict[str, list] = {t.name: [] for t in schema.tables}
    children_of: dict[str, list] = {t.name: [] for t in schema.tables}

    def add(child: str, parent: str, pairs):
        parents_of.setdefault(child, []).append((parent, pairs))
        children_of.setdefault(parent, []).append((child, pairs))

    for t in schema.tables:
        for fk in t.foreign_keys:
            add(t.name, fk.ref_table, fk.column_pairs)
    if include_implied:
        from core.implied import find_implied_fks
        for ifk in find_implied_fks(schema):
            add(ifk.table, ifk.ref_table, ((ifk.column, ifk.ref_column),))
    return parents_of, children_of


def _toposort(names: set, parents_of) -> list:
    """Parents before children, stable by name; cycle leftovers appended by name."""
    indeg = {n: 0 for n in names}
    adj: dict[str, set] = {n: set() for n in names}
    for child in names:
        for parent, _ in parents_of.get(child, []):
            if parent in names and parent != child and child not in adj[parent]:
                adj[parent].add(child)
                indeg[child] += 1
    heap = [n for n in names if indeg[n] == 0]
    heapq.heapify(heap)
    order: list = []
    while heap:
        n = heapq.heappop(heap)
        order.append(n)
        for c in sorted(adj[n]):
            indeg[c] -= 1
            if indeg[c] == 0:
                heapq.heappush(heap, c)
    order.extend(sorted(n for n in names if n not in order))
    return order


def compute_subset(schema: Schema, start_table: str, *,
                   include_implied: bool = False, max_depth: int = 5) -> SubsetResult:
    """Compute the referential footprint of ``start_table`` (down-then-up)."""
    known = {t.name for t in schema.tables}
    if start_table not in known:
        raise ValueError(f"unknown table: {start_table}")
    parents_of, children_of = _adjacency(schema, include_implied)

    # table -> (edge | None, depth). Root first.
    deriv: dict[str, tuple] = {start_table: (None, 0)}
    truncated = False

    # Phase 1: downward (dependents) — depth-limited.
    dq = deque([(start_table, 0)])
    downward = [start_table]
    while dq:
        cur, d = dq.popleft()
        if d >= max_depth:
            if children_of.get(cur):
                truncated = True
            continue
        for child, pairs in children_of.get(cur, []):
            if child not in known or child in deriv:
                continue
            deriv[child] = (SubsetEdge(cur, pairs, child, "child"), d + 1)
            downward.append(child)
            dq.append((child, d + 1))

    # Phase 2: upward (lookups) from root ∪ downward — no re-descent, unbounded
    # (referential completeness; the visited guard keeps it finite).
    dq = deque((t, deriv[t][1]) for t in downward)
    while dq:
        cur, d = dq.popleft()
        for parent, pairs in parents_of.get(cur, []):
            if parent not in known or parent in deriv:
                continue
            deriv[parent] = (SubsetEdge(cur, pairs, cur, "parent"), d + 1)
            dq.append((parent, d + 1))

    order = _toposort(set(deriv), parents_of)
    tables = tuple(
        SubsetTable(name, deriv[name][0], deriv[name][1]) for name in order
    )
    return SubsetResult(start_table, tables, truncated)


_ALLOWED_OPS = {"=", "!=", "<", ">", "<=", ">=", "IN"}


@dataclass(frozen=True)
class SubsetScript:
    table: str
    sql: str
    params: dict


def _chain(table: str, edges: dict) -> list:
    """Tables from ``table`` up to the root, following derivation edges."""
    chain = [table]
    while edges[chain[-1]] is not None:
        chain.append(edges[chain[-1]].via_table)
    return chain


def generate_subset_sql(schema: Schema, result: SubsetResult, root_filter: dict, *,
                        dialect: Dialect = SQLITE, schema_name: str = "") -> tuple:
    """Render one parameterised SELECT per closure table, joining back to the
    root table along its derivation path and filtering by ``root_filter``.
    Executes nothing."""
    op = root_filter["op"]
    if op not in _ALLOWED_OPS:
        raise ValueError(f"unsupported operator: {op}")
    col = dialect.quote(root_filter["column"])
    if op == "IN":
        vals = root_filter["value"]
        if not isinstance(vals, (list, tuple)) or not vals:
            raise ValueError("IN requires a non-empty list value")
        keys = [f"root{i}" for i in range(len(vals))]
        params_template = dict(zip(keys, vals))
        where_tail = "IN (" + ", ".join(f":{k}" for k in keys) + ")"
    else:
        params_template = {"root": root_filter["value"]}
        where_tail = f"{op} :root"

    edges = {t.name: t.edge for t in result.tables}
    scripts = []
    for st in result.tables:
        chain = _chain(st.name, edges)                 # [T, via, …, root]
        chain_edges = [edges[chain[i]] for i in range(len(chain) - 1)]
        distinct = any(e.kind == "parent" for e in chain_edges)
        alias = {i: f"t{i}" for i in range(len(chain))}

        joins = []
        for i, e in enumerate(chain_edges):
            a, b = chain[i], chain[i + 1]              # a.edge points to b (via)
            child_alias = alias[i] if e.child_table == a else alias[i + 1]
            parent_alias = alias[i + 1] if e.child_table == a else alias[i]
            conds = " AND ".join(
                f"{child_alias}.{dialect.quote(lc)} = {parent_alias}.{dialect.quote(rc)}"
                for lc, rc in e.pairs
            )
            joins.append(f"JOIN {dialect.table_ref(b, schema_name)} {alias[i + 1]} ON {conds}")

        root_alias = alias[len(chain) - 1]
        select = "SELECT DISTINCT t0.*" if distinct else "SELECT t0.*"
        lines = [select, f"FROM {dialect.table_ref(chain[0], schema_name)} t0"]
        lines += joins
        lines.append(f"WHERE {root_alias}.{col} {where_tail}")
        scripts.append(SubsetScript(st.name, "\n".join(lines) + ";", dict(params_template)))
    return tuple(scripts)


def count_sql(inner_sql: str) -> str:
    """Wrap a subset SELECT into a read-only row-count query.

    ``SELECT COUNT(*) FROM (<inner>) subset_cnt`` — the alias carries no ``AS``
    so it is valid across SQLite/PostgreSQL/MySQL/MSSQL and Oracle (Oracle
    forbids ``AS`` for a table alias; the others require an alias for the
    derived table). A trailing ';' is stripped before embedding.
    """
    inner = inner_sql.strip().rstrip(";").rstrip()
    return f"SELECT COUNT(*) FROM ({inner}) subset_cnt"


def subset_keys(pk_columns, columns, rows) -> list:
    """Order-preserving deduplicated primary-key tuples from dump rows.

    Returns [] when the table has no primary key, a PK column is absent from
    ``columns``, or there are no rows.
    """
    if not pk_columns:
        return []
    try:
        idx = [columns.index(c) for c in pk_columns]
    except ValueError:
        return []
    seen = set()
    out = []
    for r in rows:
        k = tuple(r[i] for i in idx)
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _sql_literal(v, dialect: Dialect) -> str:
    """Render a Python value as a SQL literal for a read-only artifact.

    Numbers are emitted raw; strings are single-quoted with ' doubled; None
    becomes NULL; bool becomes 1/0 (portable). The result is never executed
    by this tool — it is generated for external inspection/use.
    """
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, numbers.Number):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def subset_in_list_sql(table, pk_columns, columns, rows, *,
                       dialect: Dialect = SQLITE, schema_name: str = "") -> "str | None":
    """Render a self-contained read-only SELECT reproducing exactly the subset
    rows of ``table`` by their concrete primary keys. None when there is no PK
    or no rows. Composite keys use the portable ``(a=… AND b=…) OR …`` form.
    Executes nothing.
    """
    keys = subset_keys(pk_columns, columns, rows)
    if not keys:
        return None
    tref = dialect.table_ref(table, schema_name)
    if len(pk_columns) == 1:
        col = dialect.quote(pk_columns[0])
        lits = ", ".join(_sql_literal(k[0], dialect) for k in keys)
        where = f"{col} IN ({lits})"
    else:
        qcols = [dialect.quote(c) for c in pk_columns]
        terms = []
        for k in keys:
            parts = [
                f"{qc} IS NULL" if val is None else f"{qc} = {_sql_literal(val, dialect)}"
                for qc, val in zip(qcols, k)
            ]
            terms.append("(" + " AND ".join(parts) + ")")
        where = " OR ".join(terms)
    return f"SELECT * FROM {tref} WHERE {where};"
