"""Render a JoinPath + selections + filters into read-only SQL text.

Never executes anything. Filter values become named placeholders (:p0, :p1, …)
returned separately in `params`, so callers can show parameterized SQL and the
generated string is never a string-concatenation injection vector.
"""
from dataclasses import dataclass

from core.pathfinder import JoinPath

_ALLOWED_OPS = {"=", "!=", "<", ">", "<=", ">=", "LIKE",
                "IS NULL", "IS NOT NULL", "IN", "BETWEEN"}
_NULL_OPS = frozenset({"IS NULL", "IS NOT NULL"})
_ALLOWED_DIRECTIONS = frozenset({"ASC", "DESC"})


@dataclass(frozen=True)
class Selection:
    table: str
    column: str


@dataclass(frozen=True)
class Filter:
    table: str
    column: str
    op: str
    value: object  # None for IS (NOT) NULL; list for IN; 2-tuple for BETWEEN; scalar otherwise


@dataclass(frozen=True)
class GeneratedSQL:
    sql: str
    params: dict[str, object]


def generate_sql(path: JoinPath, selects: tuple[Selection, ...],
                 filters: tuple[Filter, ...] = (),
                 *,
                 distinct: bool = False,
                 order_by: tuple[tuple[str, str, str], ...] = (),
                 limit: "int | None" = None) -> GeneratedSQL:
    """Generate read-only SELECT SQL from a JoinPath with optional filters.

    Args:
        path: A JoinPath whose tables[0] becomes the FROM table and whose
            steps each produce one JOIN clause.
        selects: Sequence of Selection(table, column) items to include in
            the SELECT list. Must not be empty.
        filters: Optional sequence of Filter(table, column, op, value) items.
            Supported operators: =, !=, <, >, <=, >=, LIKE (scalar value),
            IS NULL / IS NOT NULL (value ignored, no placeholder),
            IN (value must be a list, each item gets its own placeholder),
            BETWEEN (value must be a 2-sequence [lo, hi]).
        distinct: If True, renders SELECT DISTINCT.
        order_by: Sequence of (table, column, direction) triples.
            direction must be 'ASC' or 'DESC' (case-insensitive).
        limit: If a positive integer, appends LIMIT n.

    Returns:
        A GeneratedSQL with the SQL string and a params dict mapping each
        placeholder name to its value.

    Raises:
        ValueError: If selects is empty, a filter uses an unsupported operator,
            an ORDER BY direction is invalid, or LIMIT is non-integer.
    """
    if not selects:
        raise ValueError("At least one selection is required.")

    distinct_kw = "DISTINCT " if distinct else ""
    select_cols = ", ".join(f"{s.table}.{s.column}" for s in selects)
    base = path.tables[0]
    lines = [f"SELECT {distinct_kw}{select_cols}", f"FROM {base}"]

    for step in path.steps:
        on = f"{step.left_table}.{step.left_col} = {step.right_table}.{step.right_col}"
        lines.append(f"JOIN {step.right_table} ON {on}")

    params: dict = {}
    if filters:
        clauses = []
        for i, flt in enumerate(filters):
            if flt.op not in _ALLOWED_OPS:
                raise ValueError(f"Unsupported operator: {flt.op}")
            if flt.op in _NULL_OPS:
                # IS NULL / IS NOT NULL: no value, no placeholder
                clauses.append(f"{flt.table}.{flt.column} {flt.op}")
            elif flt.op == "IN":
                vals = list(flt.value) if flt.value else []
                if not vals:
                    continue  # skip degenerate empty IN
                ph = []
                for j, v in enumerate(vals):
                    key = f"p{i}_{j}"
                    ph.append(f":{key}")
                    params[key] = v
                clauses.append(f"{flt.table}.{flt.column} IN ({', '.join(ph)})")
            elif flt.op == "BETWEEN":
                lo_key = f"p{i}_lo"
                hi_key = f"p{i}_hi"
                clauses.append(
                    f"{flt.table}.{flt.column} BETWEEN :{lo_key} AND :{hi_key}")
                params[lo_key] = flt.value[0]
                params[hi_key] = flt.value[1]
            else:
                key = f"p{i}"
                clauses.append(f"{flt.table}.{flt.column} {flt.op} :{key}")
                params[key] = flt.value
        if clauses:
            lines.append("WHERE " + " AND ".join(clauses))

    if order_by:
        ob_parts = []
        for tbl, col, direction in order_by:
            direction_upper = direction.upper()
            if direction_upper not in _ALLOWED_DIRECTIONS:
                raise ValueError(f"Unsupported ORDER BY direction: {direction!r}")
            ob_parts.append(f"{tbl}.{col} {direction_upper}")
        lines.append("ORDER BY " + ", ".join(ob_parts))

    if limit is not None:
        try:
            n = int(limit)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid LIMIT value: {limit!r}")
        if n > 0:
            lines.append(f"LIMIT {n}")

    return GeneratedSQL(sql="\n".join(lines), params=params)
