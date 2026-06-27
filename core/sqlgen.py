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


def _looks_numeric(s: str) -> bool:
    """True if ``s`` is a plain integer/decimal that can safely render as a bare
    SQL number. Leading-zero strings (e.g. ZIP/IDs like ``01234``) and the
    float specials inf/nan are treated as non-numeric so they stay quoted."""
    t = s.strip()
    if not t:
        return False
    if len(t) > 1 and t[0] == "0" and t[1].isdigit():
        return False  # preserve leading zeros — they are identifiers, not numbers
    try:
        int(t)
        return True
    except ValueError:
        pass
    try:
        float(t)
        return t.lower().lstrip("+-") not in ("inf", "nan", "infinity")
    except ValueError:
        return False


def _inline_literal(value: object, *, force_string: bool = False) -> str:
    """Render a filter value as a standard-SQL literal for the *display/copy*
    string only — so a pasted statement is directly runnable. The parameterised
    form (``:p0`` + ``params``) stays the execution path and the injection-safe
    contract. Numbers render bare; everything else is a single-quoted string with
    ``'`` doubled; None becomes NULL. ``force_string`` keeps a numeric-looking
    value quoted (LIKE operands are always strings)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    s = str(value)
    if not force_string and _looks_numeric(s):
        return s.strip()
    return "'" + s.replace("'", "''") + "'"


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
    # Same statement with filter values inlined as literals (for copy/display);
    # directly runnable in an external SQL client. `sql` + `params` stay the
    # parameterised execution path. Identical to `sql` when there are no filters.
    sql_inline: str = ""


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
        clauses = []         # parameterised (:p0) — execution path
        clauses_inline = []  # literal values — copy/display path
        for i, flt in enumerate(filters):
            if flt.op not in _ALLOWED_OPS:
                raise ValueError(f"Unsupported operator: {flt.op}")
            col = dialect.qualify(flt.table, flt.column)
            force_str = flt.op == "LIKE"
            if flt.op in _NULL_OPS:
                # IS NULL / IS NOT NULL: no value, no placeholder
                clauses.append(f"{col} {flt.op}")
                clauses_inline.append(f"{col} {flt.op}")
            elif flt.op == "IN":
                vals = list(flt.value) if flt.value else []
                if not vals:
                    continue  # skip degenerate empty IN
                ph = []
                lits = []
                for j, v in enumerate(vals):
                    key = f"p{i}_{j}"
                    ph.append(f":{key}")
                    lits.append(_inline_literal(v))
                    params[key] = v
                clauses.append(f"{col} IN ({', '.join(ph)})")
                clauses_inline.append(f"{col} IN ({', '.join(lits)})")
            elif flt.op == "BETWEEN":
                lo_key = f"p{i}_lo"
                hi_key = f"p{i}_hi"
                clauses.append(f"{col} BETWEEN :{lo_key} AND :{hi_key}")
                clauses_inline.append(
                    f"{col} BETWEEN {_inline_literal(flt.value[0])} "
                    f"AND {_inline_literal(flt.value[1])}")
                params[lo_key] = flt.value[0]
                params[hi_key] = flt.value[1]
            else:
                key = f"p{i}"
                clauses.append(f"{col} {flt.op} :{key}")
                clauses_inline.append(
                    f"{col} {flt.op} {_inline_literal(flt.value, force_string=force_str)}")
                params[key] = flt.value
        if clauses:
            lines.append("WHERE " + " AND ".join(clauses))

    # Branch the inline variant off here: it shares every non-WHERE line with the
    # parameterised form and only swaps the WHERE clause's placeholders for
    # literals. The WHERE (if any) was just appended, so it is the last line.
    inline_lines = list(lines)
    if filters and clauses:
        inline_lines[-1] = "WHERE " + " AND ".join(clauses_inline)

    if order_by:
        ob_parts = []
        for tbl, col, direction in order_by:
            direction_upper = direction.upper()
            if direction_upper not in _ALLOWED_DIRECTIONS:
                raise ValueError(f"Unsupported ORDER BY direction: {direction!r}")
            ob_parts.append(f"{dialect.qualify(tbl, col)} {direction_upper}")
        ob_line = "ORDER BY " + ", ".join(ob_parts)
        lines.append(ob_line)
        inline_lines.append(ob_line)

    if n is not None:
        limit_line = None
        if dialect.limit_style == "limit":
            limit_line = f"LIMIT {n}"
        elif dialect.limit_style == "fetch_first":
            limit_line = f"FETCH FIRST {n} ROWS ONLY"
        # "top" was already injected into the SELECT clause above.
        if limit_line:
            lines.append(limit_line)
            inline_lines.append(limit_line)

    return GeneratedSQL(sql="\n".join(lines), params=params,
                        sql_inline="\n".join(inline_lines))
