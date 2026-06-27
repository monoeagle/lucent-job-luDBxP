"""Read-only analysis of a single SQL statement via its sqlglot AST.

Never executes anything against a database. Parses the statement, classifies
it, extracts the tables it reads and writes, and (in later layers) derives
non-blocking warnings. On a parse failure no exception escapes: parse_error
is set and the other fields stay empty.
"""
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

# Map sqlglot root expression types to a coarse, user-facing statement type.
_DDL_NODES = (exp.Create, exp.Drop, exp.Alter)
_TYPE_NAMES = {
    exp.Select: "SELECT",
    exp.Insert: "INSERT",
    exp.Update: "UPDATE",
    exp.Delete: "DELETE",
}


@dataclass(frozen=True)
class AnalysisWarning:
    level: str    # "info" | "warn" | "danger"
    code: str     # stable machine code, e.g. "WRITE_STATEMENT"
    message: str  # German user-facing text


@dataclass(frozen=True)
class AnalysisResult:
    statement_type: str
    tables_read: tuple[str, ...]
    tables_written: tuple[str, ...]
    warnings: tuple[AnalysisWarning, ...]
    parse_error: "str | None"


def _statement_type(node) -> str:
    if isinstance(node, _DDL_NODES):
        return "DDL"
    for cls, name in _TYPE_NAMES.items():
        if isinstance(node, cls):
            return name
    return "OTHER"


def _written_table(node) -> "str | None":
    """The single table a write statement targets, or None for reads."""
    if isinstance(node, (exp.Insert, *_DDL_NODES)):
        tgt = node.find(exp.Table)
        return tgt.name if tgt else None
    if isinstance(node, (exp.Update, exp.Delete)):
        tgt = node.this
        return tgt.name if isinstance(tgt, exp.Table) else None
    return None


def analyze(sql: str, schema=None, dialect: "str | None" = None) -> AnalysisResult:
    """Analyze one SQL statement read-only. Never executes it.

    Args:
        sql: The statement text.
        schema: Optional core.model.Schema for table/column cross-checks. When
            None, schema-dependent warnings are skipped (text-only mode).
        dialect: Optional sqlglot dialect name; None parses dialect-neutrally.

    Returns:
        An AnalysisResult. On parse failure, parse_error is set and the type is
        "OTHER" with empty table lists.
    """
    try:
        node = sqlglot.parse_one(sql, read=dialect)
    except SqlglotError as exc:
        return AnalysisResult("OTHER", (), (), (), str(exc))
    if node is None:
        return AnalysisResult("OTHER", (), (), (), "empty statement")

    written_name = _written_table(node)
    written = {written_name} if written_name else set()
    read = {t.name for t in node.find_all(exp.Table)} - written

    return AnalysisResult(
        statement_type=_statement_type(node),
        tables_read=tuple(sorted(read)),
        tables_written=tuple(sorted(written)),
        warnings=(),
        parse_error=None,
    )
