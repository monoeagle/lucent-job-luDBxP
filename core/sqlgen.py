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
class Dialect:
    """SQL-dialect rules for read-only SELECT rendering (AP-29).

    Only the parts that actually differ between backends: identifier quoting
    and row limiting. ``limit_style`` is one of ``"limit"`` (suffix
    ``LIMIT n``), ``"top"`` (``SELECT TOP n …``) or ``"fetch_first"``
    (suffix ``FETCH FIRST n ROWS ONLY``).
    """
    name: str
    quote_open: str
    quote_close: str
    limit_style: str

    def quote(self, ident: str) -> str:
        """Quote one identifier, escaping the closing char by doubling it."""
        return (self.quote_open
                + ident.replace(self.quote_close, self.quote_close * 2)
                + self.quote_close)

    def qualify(self, table: str, column: str) -> str:
        """Render a quoted ``table.column`` reference."""
        return f"{self.quote(table)}.{self.quote(column)}"


SQLITE   = Dialect("sqlite", '"', '"', "limit")
POSTGRES = Dialect("postgresql", '"', '"', "limit")
MYSQL    = Dialect("mysql", "`", "`", "limit")
MSSQL    = Dialect("mssql", "[", "]", "top")
ORACLE   = Dialect("oracle", '"', '"', "fetch_first")

DIALECTS = {d.name: d for d in (SQLITE, POSTGRES, MYSQL, MSSQL, ORACLE)}


def dialect_for(db_type: "str | None") -> Dialect:
    """Resolve a connection's ``db_type`` to a Dialect; SQLite is the fallback."""
    return DIALECTS.get((db_type or "").strip().lower(), SQLITE)


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
                 limit: "int | None" = None,
                 dialect: Dialect = SQLITE) -> GeneratedSQL:
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

    # Resolve the row limit once — used both for the SELECT TOP prefix (MSSQL)
    # and the suffix forms (LIMIT / FETCH FIRST). n is None when no positive cap.
    n = None
    if limit is not None:
        try:
            n = int(limit)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid LIMIT value: {limit!r}")
        if n <= 0:
            n = None

    distinct_kw = "DISTINCT " if distinct else ""
    top_kw = f"TOP {n} " if (n is not None and dialect.limit_style == "top") else ""
    select_cols = ", ".join(dialect.qualify(s.table, s.column) for s in selects)
    base = dialect.quote(path.tables[0])
    lines = [f"SELECT {distinct_kw}{top_kw}{select_cols}", f"FROM {base}"]

    for step in path.steps:
        on = " AND ".join(
            f"{dialect.qualify(step.left_table, lc)} = "
            f"{dialect.qualify(step.right_table, rc)}"
            for lc, rc in step.column_pairs
        )
        lines.append(f"JOIN {dialect.quote(step.right_table)} ON {on}")

    params: dict = {}
    if filters:
        clauses = []
        for i, flt in enumerate(filters):
            if flt.op not in _ALLOWED_OPS:
                raise ValueError(f"Unsupported operator: {flt.op}")
            col = dialect.qualify(flt.table, flt.column)
            if flt.op in _NULL_OPS:
                # IS NULL / IS NOT NULL: no value, no placeholder
                clauses.append(f"{col} {flt.op}")
            elif flt.op == "IN":
                vals = list(flt.value) if flt.value else []
                if not vals:
                    continue  # skip degenerate empty IN
                ph = []
                for j, v in enumerate(vals):
                    key = f"p{i}_{j}"
                    ph.append(f":{key}")
                    params[key] = v
                clauses.append(f"{col} IN ({', '.join(ph)})")
            elif flt.op == "BETWEEN":
                lo_key = f"p{i}_lo"
                hi_key = f"p{i}_hi"
                clauses.append(f"{col} BETWEEN :{lo_key} AND :{hi_key}")
                params[lo_key] = flt.value[0]
                params[hi_key] = flt.value[1]
            else:
                key = f"p{i}"
                clauses.append(f"{col} {flt.op} :{key}")
                params[key] = flt.value
        if clauses:
            lines.append("WHERE " + " AND ".join(clauses))

    if order_by:
        ob_parts = []
        for tbl, col, direction in order_by:
            direction_upper = direction.upper()
            if direction_upper not in _ALLOWED_DIRECTIONS:
                raise ValueError(f"Unsupported ORDER BY direction: {direction!r}")
            ob_parts.append(f"{dialect.qualify(tbl, col)} {direction_upper}")
        lines.append("ORDER BY " + ", ".join(ob_parts))

    if n is not None:
        if dialect.limit_style == "limit":
            lines.append(f"LIMIT {n}")
        elif dialect.limit_style == "fetch_first":
            lines.append(f"FETCH FIRST {n} ROWS ONLY")
        # "top" was already injected into the SELECT clause above.

    return GeneratedSQL(sql="\n".join(lines), params=params)
