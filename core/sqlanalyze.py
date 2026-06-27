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

    warnings: list[AnalysisWarning] = []
    stmt_type = _statement_type(node)

    if stmt_type in ("INSERT", "UPDATE", "DELETE", "DDL"):
        warnings.append(AnalysisWarning(
            "danger", "WRITE_STATEMENT",
            "Dieses Statement würde Daten bzw. das Schema verändern — "
            "das Tool führt es nicht aus."))

    if isinstance(node, (exp.Update, exp.Delete)) and node.find(exp.Where) is None:
        warnings.append(AnalysisWarning(
            "danger", "NO_WHERE",
            "UPDATE/DELETE ohne WHERE — betrifft alle Zeilen der Tabelle."))

    # Cartesian heuristic: a JOIN/comma-join without ON/USING and no WHERE to
    # link the tables. A present WHERE is assumed to provide the link.
    joins_without_on = any(
        j.args.get("on") is None and j.args.get("using") is None
        for j in node.find_all(exp.Join)
    )
    if joins_without_on and node.find(exp.Where) is None:
        warnings.append(AnalysisWarning(
            "warn", "CARTESIAN_JOIN",
            "Join ohne Verknüpfungsbedingung — möglicher kartesischer Join "
            "(Zeilen-Explosion)."))

    if schema is not None:
        known = {t.name.lower() for t in schema.tables}
        known |= {v.name.lower() for v in getattr(schema, "views", ())}
        # Map alias -> real table name for qualified-column resolution.
        alias_to_table: dict[str, str] = {}
        for tbl in node.find_all(exp.Table):
            real = tbl.name
            alias_to_table[real.lower()] = real
            alias = tbl.alias
            if alias:
                alias_to_table[alias.lower()] = real
            if real.lower() not in known:
                warnings.append(AnalysisWarning(
                    "warn", "UNKNOWN_TABLE",
                    f'Tabelle „{real}" ist im verbundenen Schema nicht vorhanden.'))
        # Qualified columns only (table.column); unqualified columns are skipped.
        for col in node.find_all(exp.Column):
            tbl_ref = col.table
            if not tbl_ref:
                continue
            real = alias_to_table.get(tbl_ref.lower())
            if real is None or real.lower() not in known:
                continue  # unknown table already warned; don't double-warn
            if not schema.has_column(real, col.name):
                warnings.append(AnalysisWarning(
                    "warn", "UNKNOWN_COLUMN",
                    f'Spalte „{col.name}" existiert nicht in Tabelle „{real}".'))

    return AnalysisResult(
        statement_type=stmt_type,
        tables_read=tuple(sorted(read)),
        tables_written=tuple(sorted(written)),
        warnings=tuple(warnings),
        parse_error=None,
    )
