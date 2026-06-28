"""Render a JoinPath + selections + filters into read-only SQL text.

Never executes anything. Filter values become named placeholders (:p0, :p1, …)
returned separately in `params`, so callers can show parameterized SQL and the
generated string is never a string-concatenation injection vector.
"""
from dataclasses import dataclass

from core.pathfinder import JoinPath

# Per-step join type (AP-41). INNER is the default; outer joins keep rows from
# the driving side even without a match on the joined table.
_JOIN_KEYWORDS = {
    "INNER": "JOIN", "LEFT": "LEFT JOIN", "RIGHT": "RIGHT JOIN", "FULL": "FULL JOIN",
}

_ALLOWED_OPS = {"=", "!=", "<", ">", "<=", ">=", "LIKE",
                "IS NULL", "IS NOT NULL", "IN", "BETWEEN"}
_NULL_OPS = frozenset({"IS NULL", "IS NOT NULL"})
_ALLOWED_DIRECTIONS = frozenset({"ASC", "DESC"})

# Aggregate comparison operators allowed inside a HAVING clause (scalar only).
_ALLOWED_HAVING_OPS = frozenset({"=", "!=", "<", ">", "<=", ">="})

# Tier-3: aggregate functions allowed on a Selection. Empty agg = no aggregate.
_ALLOWED_AGGS = frozenset({"COUNT", "SUM", "AVG", "MIN", "MAX"})


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

    def table_ref(self, table: str, schema: str = "") -> str:
        """Quoted table reference, schema-qualified when ``schema`` is non-empty."""
        return f"{self.quote(schema)}.{self.quote(table)}" if schema else self.quote(table)

    def qualify(self, table: str, column: str, schema: str = "") -> str:
        """Render a quoted ``[schema.]table.column`` reference."""
        return f"{self.table_ref(table, schema)}.{self.quote(column)}"


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
    agg: str = ""   # "" = plain column; else one of _ALLOWED_AGGS -> FUNC(col)


@dataclass(frozen=True)
class Filter:
    table: str
    column: str
    op: str
    value: object  # None for IS (NOT) NULL; list for IN; 2-tuple for BETWEEN; scalar otherwise


@dataclass(frozen=True)
class Having:
    table: str
    column: str
    agg: str       # required; one of _ALLOWED_AGGS
    op: str        # one of _ALLOWED_HAVING_OPS
    value: object  # scalar; rendered as a named placeholder :h{i}


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
                 order_by: tuple[tuple, ...] = (),
                 having: tuple[Having, ...] = (),
                 limit: "int | None" = None,
                 join_types: tuple[str, ...] = (),
                 dialect: Dialect = SQLITE,
                 schema: str = "") -> GeneratedSQL:
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

    # AP-43: readable multi-line layout — one column / one ON-condition per line,
    # "=" aligned within a composite ON, so lines stay short (no horizontal scroll)
    # and a pasted statement is clean. The single-line `lines` head holds
    # SELECT … FROM … JOIN …; WHERE/ORDER/LIMIT are appended further down.
    head = "SELECT"
    if distinct:
        head += " DISTINCT"
    if n is not None and dialect.limit_style == "top":
        head += f" TOP {n}"
    lines = [head]
    for k, s in enumerate(selects):
        comma = "," if k < len(selects) - 1 else ""
        expr = dialect.qualify(s.table, s.column, schema)
        if s.agg:
            if s.agg not in _ALLOWED_AGGS:
                raise ValueError(f"Unsupported aggregate: {s.agg!r}")
            expr = f"{s.agg}({expr})"
        lines.append(f"    {expr}{comma}")
    lines.append(f"FROM {dialect.table_ref(path.tables[0], schema)}")

    for i, step in enumerate(path.steps):
        jt = (join_types[i] if i < len(join_types) else "INNER") or "INNER"
        kw = _JOIN_KEYWORDS.get(jt.upper())
        if kw is None:
            raise ValueError(f"Unsupported join type: {jt!r}")
        lines.append(f"{kw} {dialect.table_ref(step.right_table, schema)}")
        pairs = [(dialect.qualify(step.left_table, lc, schema),
                  dialect.qualify(step.right_table, rc, schema))
                 for lc, rc in step.column_pairs]
        width = max(len(lhs) for lhs, _ in pairs)
        for j, (lhs, rhs) in enumerate(pairs):
            prefix = "    ON " if j == 0 else "   AND "
            lines.append(f"{prefix}{lhs.ljust(width)} = {rhs}")

    params: dict = {}
    clauses = []         # parameterised (:p0) — execution path
    clauses_inline = []  # literal values — copy/display path
    if filters:
        for i, flt in enumerate(filters):
            if flt.op not in _ALLOWED_OPS:
                raise ValueError(f"Unsupported operator: {flt.op}")
            col = dialect.qualify(flt.table, flt.column, schema)
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
    # WHERE: first condition on the WHERE line, each further one on its own
    # "  AND …" line (mirrors the JOIN ON/AND style). The parameterised and the
    # value-inlined variants differ only in these clauses.
    def _where_block(cls):
        return [(f"WHERE {c}" if k == 0 else f"  AND {c}")
                for k, c in enumerate(cls)]

    where_param = _where_block(clauses) if clauses else []
    where_inline = _where_block(clauses_inline) if clauses_inline else []

    # ORDER BY / LIMIT are identical in both variants (no filter values).
    tail: list[str] = []
    if order_by:
        ob_parts = []
        for entry in order_by:
            tbl, col, direction = entry[0], entry[1], entry[2]
            agg = entry[3] if len(entry) > 3 else ""
            direction_upper = direction.upper()
            if direction_upper not in _ALLOWED_DIRECTIONS:
                raise ValueError(f"Unsupported ORDER BY direction: {direction!r}")
            expr = dialect.qualify(tbl, col, schema)
            if agg:
                if agg not in _ALLOWED_AGGS:
                    raise ValueError(f"Unsupported aggregate: {agg!r}")
                expr = f"{agg}({expr})"
            ob_parts.append(f"{expr} {direction_upper}")
        tail.append("ORDER BY " + ", ".join(ob_parts))

    if n is not None:
        if dialect.limit_style == "limit":
            tail.append(f"LIMIT {n}")
        elif dialect.limit_style == "fetch_first":
            tail.append(f"FETCH FIRST {n} ROWS ONLY")
        # "top" was already injected into the SELECT head above.

    # Tier-3 auto-GROUP-BY: group by every non-aggregated select, but only when
    # at least one select IS aggregated (else this is a plain row query). All
    # columns aggregated -> empty group_cols -> single-row aggregate, no GROUP BY.
    group_lines: list[str] = []
    has_agg = any(s.agg for s in selects)
    group_cols = [s for s in selects if not s.agg]
    if has_agg and group_cols:
        parts = [dialect.qualify(s.table, s.column, schema) for s in group_cols]
        group_lines.append("GROUP BY " + ", ".join(parts))

    # HAVING: filter groups by an aggregate. Mandatory aggregate, scalar ops,
    # parametrised value (:h{i}) in its own namespace so it never collides with
    # WHERE's :p{i}. Clause order: after GROUP BY, before ORDER BY/LIMIT.
    having_clauses = []
    having_inline = []
    for i, h in enumerate(having):
        if h.op not in _ALLOWED_HAVING_OPS:
            raise ValueError(f"Unsupported HAVING operator: {h.op}")
        if h.agg not in _ALLOWED_AGGS:
            raise ValueError(f"HAVING requires an aggregate, got: {h.agg!r}")
        expr = f"{h.agg}({dialect.qualify(h.table, h.column, schema)})"
        key = f"h{i}"
        having_clauses.append(f"{expr} {h.op} :{key}")
        having_inline.append(f"{expr} {h.op} {_inline_literal(h.value)}")
        params[key] = h.value

    def _having_block(cls):
        return [(f"HAVING {c}" if k == 0 else f"  AND {c}")
                for k, c in enumerate(cls)]

    having_param = _having_block(having_clauses) if having_clauses else []
    having_inline_block = _having_block(having_inline) if having_inline else []

    sql = "\n".join(lines + where_param + group_lines + having_param + tail)
    # The copy/display variant ends with a semicolon so it pastes-and-runs cleanly;
    # the executed (parameterised) `sql` stays without one.
    sql_inline = "\n".join(lines + where_inline + group_lines + having_inline_block + tail) + ";"
    return GeneratedSQL(sql=sql, params=params, sql_inline=sql_inline)
