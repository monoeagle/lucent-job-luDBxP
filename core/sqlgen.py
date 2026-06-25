"""Render a JoinPath + selections + filters into read-only SQL text.

Never executes anything. Filter values become named placeholders (:p0, :p1, …)
returned separately in `params`, so callers can show parameterized SQL and the
generated string is never a string-concatenation injection vector.
"""
from dataclasses import dataclass

from core.pathfinder import JoinPath

_ALLOWED_OPS = {"=", "!=", "<", ">", "<=", ">=", "LIKE"}


@dataclass(frozen=True)
class Selection:
    table: str
    column: str


@dataclass(frozen=True)
class Filter:
    table: str
    column: str
    op: str
    value: object


@dataclass(frozen=True)
class GeneratedSQL:
    sql: str
    params: dict[str, object]


def generate_sql(path: JoinPath, selects: tuple[Selection, ...],
                 filters: tuple[Filter, ...] = ()) -> GeneratedSQL:
    """Generate read-only SELECT SQL from a JoinPath with optional filters.

    Args:
        path: A JoinPath whose tables[0] becomes the FROM table and whose
            steps each produce one JOIN clause.
        selects: Sequence of Selection(table, column) items to include in
            the SELECT list. Must not be empty.
        filters: Optional sequence of Filter(table, column, op, value) items.
            Each filter value is emitted as a named placeholder (:p0, :p1, …)
            and returned in GeneratedSQL.params — never inlined into the SQL
            string.

    Returns:
        A GeneratedSQL with the SQL string and a params dict mapping each
        placeholder name to its value.

    Raises:
        ValueError: If selects is empty or a filter uses an unsupported operator.
    """
    if not selects:
        raise ValueError("At least one selection is required.")

    select_cols = ", ".join(f"{s.table}.{s.column}" for s in selects)
    base = path.tables[0]
    lines = [f"SELECT {select_cols}", f"FROM {base}"]

    for step in path.steps:
        on = f"{step.left_table}.{step.left_col} = {step.right_table}.{step.right_col}"
        lines.append(f"JOIN {step.right_table} ON {on}")

    params: dict = {}
    if filters:
        clauses = []
        for i, flt in enumerate(filters):
            if flt.op not in _ALLOWED_OPS:
                raise ValueError(f"Unsupported operator: {flt.op}")
            key = f"p{i}"
            clauses.append(f"{flt.table}.{flt.column} {flt.op} :{key}")
            params[key] = flt.value
        lines.append("WHERE " + " AND ".join(clauses))

    return GeneratedSQL(sql="\n".join(lines), params=params)
