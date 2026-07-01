"""Read-only analysis of a single SQL statement via its sqlglot AST.

Never executes anything against a database. Parses the statement, classifies
it, extracts the tables it reads and writes, and (in later layers) derives
non-blocking warnings. On a parse failure no exception escapes: parse_error
is set and the other fields stay empty.
"""
import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

# Map this project's dialect names (core.sqlgen) to sqlglot's dialect names.
# sqlglot uses "postgres" (not "postgresql") and "tsql" (not "mssql").
# An unmapped or None dialect parses dialect-neutrally (read=None).
_SQLGLOT_DIALECT = {
    "sqlite": "sqlite",
    "postgresql": "postgres",
    "mysql": "mysql",
    "mssql": "tsql",
    "oracle": "oracle",
}

# Map sqlglot root expression types to a coarse, user-facing statement type.
_DDL_NODES = (exp.Create, exp.Drop, exp.Alter)
_TYPE_NAMES = {
    exp.Select: "SELECT",
    exp.Insert: "INSERT",
    exp.Update: "UPDATE",
    exp.Delete: "DELETE",
}


# Strips ANSI/CSI escape sequences (e.g. sqlglot's error-token underlining).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

_TOKEN_ERR_RE = re.compile(r"^Error tokenizing '(.*)'$", re.DOTALL)


@dataclass(frozen=True)
class AnalysisWarning:
    level: str    # "info" | "warn" | "danger"
    code: str     # stable machine code, e.g. "WRITE_STATEMENT"
    message: str  # German user-facing text


@dataclass(frozen=True)
class AnalysisSuggestion:
    code: str     # stabile Maschinen-Code, z. B. "DISTINCT_WITH_GROUP_BY"
    message: str  # deutscher, anzeigbarer Vorschlagstext


@dataclass(frozen=True)
class AnalysisResult:
    statement_type: str
    tables_read: tuple[str, ...]
    tables_written: tuple[str, ...]
    warnings: tuple[AnalysisWarning, ...]
    parse_error: "str | None"
    # AP-39 — structure & clause analysis (all optional, default-empty so the
    # parse-error/empty returns above stay valid 5-positional constructions).
    columns: tuple[str, ...] = ()                      # SELECT-list expressions
    joins: tuple[dict, ...] = ()                       # {kind, table, on}
    edges: tuple[tuple[str, str], ...] = ()            # table pairs for the graph
    filters: tuple[str, ...] = ()                      # WHERE predicates (split on AND)
    group_by: tuple[str, ...] = ()
    having: tuple[str, ...] = ()
    order_by: tuple[str, ...] = ()                     # "col ASC" / "col DESC"
    distinct: bool = False
    limit: "str | None" = None
    structure: dict = field(default_factory=dict)      # counts (tables, joins, …)
    complexity_score: int = 0
    complexity_grade: str = "A"
    suggestions: tuple[AnalysisSuggestion, ...] = ()  # AP-F: Optimierungs-Vorschläge
    # AP-65·A — parse-error location (None/"" when the statement parses).
    parse_error_line: "int | None" = None
    parse_error_col: "int | None" = None
    parse_error_context: str = ""       # excerpt around the offending token
    parse_error_highlight: str = ""     # the offending token (for marking)
    parse_error_highlight_pos: int = -1 # context-relative index of the token; -1 = unknown
    parse_error_hint: str = ""          # honest extra note (e.g. unclosed quote)


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


def _join_kind(join) -> str:
    """Human label for a JOIN's type, e.g. 'INNER', 'LEFT', 'LEFT OUTER', 'CROSS'."""
    side = (join.args.get("side") or "").upper()
    kind = (join.args.get("kind") or "").upper()
    label = " ".join(p for p in (side, kind) if p).strip()
    return label or "INNER"


def _alias_map(node) -> dict:
    """Map each table alias *and* real name (lowercased) to the real table name."""
    amap: dict[str, str] = {}
    for tbl in node.find_all(exp.Table):
        real = tbl.name
        amap[real.lower()] = real
        if tbl.alias:
            amap[tbl.alias.lower()] = real
    return amap


def _tables_in(expr, amap: dict) -> list:
    """Distinct real table names referenced by the columns inside an expression."""
    out: list[str] = []
    if expr is None:
        return out
    for col in expr.find_all(exp.Column):
        ref = col.table
        if not ref:
            continue
        real = amap.get(ref.lower())
        if real and real not in out:
            out.append(real)
    return out


def _split_and(predicate) -> list:
    """Flatten a boolean predicate tree into its top-level AND-separated parts."""
    if predicate is None:
        return []
    parts: list = []
    stack = [predicate]
    while stack:
        n = stack.pop()
        if isinstance(n, exp.And):
            stack.append(n.right)
            stack.append(n.left)
        else:
            parts.append(n)
    return parts


def _structure_and_complexity(node) -> "tuple[dict, int, str]":
    """Count structural features and derive a weighted complexity score + grade."""
    n_tables = len({t.name for t in node.find_all(exp.Table)})
    joins = list(node.find_all(exp.Join))
    join_kinds: dict[str, int] = {}
    for j in joins:
        join_kinds[_join_kind(j)] = join_kinds.get(_join_kind(j), 0) + 1
    # Subqueries: SELECTs nested below the root (root itself excluded).
    n_subq = sum(1 for s in node.find_all(exp.Select) if s is not node)
    n_cte = len(list(node.find_all(exp.CTE)))
    n_union = len(list(node.find_all(exp.Union)))
    n_window = len(list(node.find_all(exp.Window)))
    n_agg = len(list(node.find_all(exp.AggFunc)))
    n_case = len(list(node.find_all(exp.Case)))
    structure = {
        "tables": n_tables,
        "joins": len(joins),
        "join_kinds": join_kinds,
        "subqueries": n_subq,
        "ctes": n_cte,
        "unions": n_union,
        "window_functions": n_window,
        "aggregates": n_agg,
        "case_blocks": n_case,
    }
    score = (len(joins) * 1 + n_subq * 3 + n_cte * 2 + n_union * 1
             + n_window * 2 + n_agg * 1 + n_case * 1)
    # Grade buckets (A best … E worst).
    grade = ("A" if score <= 2 else "B" if score <= 5 else "C" if score <= 9
             else "D" if score <= 14 else "E")
    return structure, score, grade


def _within_edit1(a: str, b: str) -> bool:
    """True if a and b differ by at most one insertion/deletion/substitution."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    i = 0
    while i < min(la, lb) and a[i] == b[i]:
        i += 1
    if i == min(la, lb):
        return True                      # common prefix; one is the other + 1 char
    if la == lb:
        return a[i + 1:] == b[i + 1:]     # single substitution
    if la > lb:
        return a[i + 1:] == b[i:]         # deletion from a
    return a[i:] == b[i + 1:]             # insertion into a


# Join keywords whose typo'd form sqlglot silently swallows as a table alias
# (e.g. "FROM t LEFTI JOIN u" → table t aliased "LEFTI").
_JOIN_KEYWORD_LOOKALIKES = ("LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS")


def _static_lints(node) -> list:
    """Schema-free static-quality lints (SELECT *, non-sargable predicates, …)."""
    out: list[AnalysisWarning] = []
    if any(isinstance(e, exp.Star) for e in node.find_all(exp.Star)):
        out.append(AnalysisWarning(
            "info", "SELECT_STAR",
            "SELECT * — nur benötigte Spalten auswählen (klarer + weniger I/O)."))
    # Leading-wildcard LIKE ('%…') cannot use a normal index.
    for like in node.find_all(exp.Like):
        pat = like.expression
        if isinstance(pat, exp.Literal) and pat.is_string and pat.this.startswith("%"):
            out.append(AnalysisWarning(
                "warn", "LEADING_WILDCARD",
                "LIKE mit führendem '%' ist nicht index-nutzbar (Full Scan)."))
            break
    # A function wrapping a column inside WHERE defeats an index on that column.
    where = node.find(exp.Where)
    if where is not None:
        for fn in where.find_all(exp.Func):
            if fn.find(exp.Column) is not None:
                out.append(AnalysisWarning(
                    "info", "FUNC_ON_COLUMN",
                    "Funktion auf einer Spalte in WHERE — ein Index darauf wird ignoriert."))
                break
    # Typo heuristic: sqlglot silently parses a mistyped join keyword as a table
    # alias (LEFTI → alias). Flag aliases that closely resemble a join keyword.
    flagged = set()
    for tbl in node.find_all(exp.Table):
        alias = (tbl.alias or "")
        au = alias.upper()
        if len(au) < 4 or au in flagged:
            continue
        for kw in _JOIN_KEYWORD_LOOKALIKES:
            if au != kw and _within_edit1(au, kw):
                flagged.add(au)
                out.append(AnalysisWarning(
                    "warn", "SUSPICIOUS_ALIAS",
                    f'Tabellen-Alias „{alias}“ ähnelt dem Schlüsselwort „{kw}“ — '
                    f'möglicher Tippfehler im Join-Typ?'))
                break
    return out


def _optimization_suggestions(node) -> list:
    """Schema-freie Optimierungs-Hinweise für ein Top-Level-SELECT — neutrale
    Ratschläge, getrennt vom Warnungs-Kanal. Max. ein Vorschlag je Heuristik."""
    out: list[AnalysisSuggestion] = []
    if node.args.get("distinct") is not None and node.args.get("group") is not None:
        out.append(AnalysisSuggestion(
            "DISTINCT_WITH_GROUP_BY",
            "DISTINCT ist überflüssig — GROUP BY macht die Zeilen bereits eindeutig."))
    if node.args.get("order") is not None and node.args.get("limit") is None:
        out.append(AnalysisSuggestion(
            "ORDER_BY_NO_LIMIT",
            "ORDER BY ohne LIMIT sortiert das gesamte Ergebnis — LIMIT ergänzen, "
            "wenn nur ein Ausschnitt gebraucht wird."))
    where = node.args.get("where")
    if where is not None and any(
            o.find_ancestor(exp.Select) is node for o in where.find_all(exp.Or)):
        out.append(AnalysisSuggestion(
            "OR_IN_WHERE",
            "OR in WHERE kann die Nutzung von Indizes verhindern — "
            "IN(…) (gleiche Spalte) oder UNION erwägen."))
    if where is not None:
        for sub in where.find_all(exp.Select):
            if sub.find_ancestor(exp.Exists) is None:   # EXISTS ist bereits empfohlen
                out.append(AnalysisSuggestion(
                    "SUBQUERY_IN_WHERE",
                    "Unterabfrage in WHERE — oft als JOIN oder EXISTS "
                    "effizienter formulierbar."))
                break
    return out


def _unclosed_quote_offset(sql):
    """Return the offset of the quote (" or ') left open at end of input, else
    None. Toggles quote state; a doubled quote ('' / "") is close+open = neutral,
    which matches SQL's escaped-quote convention. Pure, read-only."""
    q = None
    open_at = None
    for i, c in enumerate(sql):
        if q is None:
            if c in ('"', "'"):
                q = c
                open_at = i
        elif c == q:
            q = None
            open_at = None
    return open_at


def _odd_quote_line(sql, quote_char):
    """Return the 1-based line number of the sole line whose count of
    ``quote_char`` is odd, or None when zero or multiple lines qualify.
    A missing quote leaves exactly that line with an odd count; doubled
    ("") escapes and balanced quotes stay even. Pure, read-only."""
    odd = [i + 1 for i, line in enumerate(sql.split("\n"))
           if line.count(quote_char) % 2 == 1]
    return odd[0] if len(odd) == 1 else None


def _parse_error_location(exc, sql):
    """Extract (line, col, context, highlight, highlight_pos, hint) from a
    sqlglot parse/token error. ParseError carries structured ``.errors``;
    TokenError does not — an unclosed quote makes the tokenizer consume to EOF,
    so we locate the quote left open at end of input and flag it. Returns
    ``(None, None, "", "", -1, "")`` when nothing usable can be extracted."""
    errors = getattr(exc, "errors", None)
    if errors:
        e = errors[0]
        start = e.get("start_context") or ""
        highlight = e.get("highlight") or ""
        context = start + highlight + (e.get("end_context") or "")
        return e.get("line"), e.get("col"), context, highlight, len(start), ""
    # TokenError: prefer the unclosed-quote scan (the common, real case).
    off = _unclosed_quote_offset(sql)
    if off is not None:
        q = sql[off]
        line = sql.count("\n", 0, off) + 1
        # Ungerade-Quote-Heuristik: die echte Fehlerzeile hat eine ungerade Anzahl
        # des offenen Quote-Zeichens. Weicht sie von der EOF-Zeile ab, dorthin
        # umleiten — ohne Spalte/Mark, da ein fehlendes Quote keine Position hat.
        odd_line = _odd_quote_line(sql, q)
        if odd_line is not None and odd_line != line:
            context = sql.split("\n")[odd_line - 1]
            hint = (f"Vermutlich fehlt ein {q} in Zeile {odd_line} — die genaue "
                    f"Position ist nicht bestimmbar (fehlendes Anführungszeichen).")
            return odd_line, None, context, "", -1, hint
        col = off - sql.rfind("\n", 0, off)          # rfind == -1 → col = off + 1
        highlight = sql[off]
        ctx_start = max(0, off - 30)
        context = sql[ctx_start:off + 10]
        hint = ("Nicht geschlossenes Anführungszeichen — markiert ist das am "
                "Statement-Ende offene Quote; bei verschobenen Quotes kann die "
                "eigentliche Ursache weiter oben liegen.")
        return line, col, context, highlight, off - ctx_start, hint
    # Balanced quotes, other tokenizer error: fall back to the message prefix.
    m = _TOKEN_ERR_RE.match(str(exc))
    if m:
        prefix = m.group(1)
        if sql.startswith(prefix):
            off = len(prefix)
            line = prefix.count("\n") + 1
            col = off - prefix.rfind("\n")
            highlight = sql[off] if off < len(sql) else ""
            ctx_start = max(0, off - 20)
            context = sql[ctx_start:off + 20]
            return line, col, context, highlight, off - ctx_start, ""
    return None, None, "", "", -1, ""


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
    read = _SQLGLOT_DIALECT.get(dialect) if dialect else None
    try:
        node = sqlglot.parse_one(sql, read=read)
    except (SqlglotError, ValueError) as exc:
        # sqlglot underlines the offending token with ANSI escape codes; strip
        # them so the browser shows clean text, not "□[4m…□[0m" garbage.
        line, col, ctx, hl, hlpos, hint = _parse_error_location(exc, sql)
        return AnalysisResult(
            "OTHER", (), (), (), _ANSI_RE.sub("", str(exc)),
            parse_error_line=line, parse_error_col=col,
            parse_error_context=ctx, parse_error_highlight=hl,
            parse_error_highlight_pos=hlpos, parse_error_hint=hint,
        )
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

    if isinstance(node, (exp.Update, exp.Delete)) and node.args.get("where") is None:
        warnings.append(AnalysisWarning(
            "danger", "NO_WHERE",
            "UPDATE/DELETE ohne WHERE — betrifft alle Zeilen der Tabelle."))

    # Cartesian heuristic: a JOIN/comma-join without ON/USING and no WHERE to
    # link the tables. A present WHERE is assumed to provide the link.
    joins_without_on = any(
        j.args.get("on") is None and j.args.get("using") is None
        for j in node.find_all(exp.Join)
    )
    if joins_without_on and node.args.get("where") is None:
        warnings.append(AnalysisWarning(
            "warn", "CARTESIAN_JOIN",
            "Join ohne Verknüpfungsbedingung — möglicher kartesischer Join "
            "(Zeilen-Explosion)."))

    if schema is not None:
        known = {t.name.lower() for t in schema.tables}
        known |= {v.name.lower() for v in getattr(schema, "views", ())}
        # Case-insensitive column index: lowercased table name -> set of lowercased column names.
        cols_by_table = {
            t.name.lower(): {c.name.lower() for c in t.columns}
            for t in schema.tables
        }
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
                    f'Tabelle „{real}“ ist im verbundenen Schema nicht vorhanden.'))
        # Qualified columns only (table.column); unqualified columns are skipped.
        for col in node.find_all(exp.Column):
            tbl_ref = col.table
            if not tbl_ref:
                continue
            real = alias_to_table.get(tbl_ref.lower())
            if real is None or real.lower() not in known:
                continue  # unknown table already warned; don't double-warn
            cols = cols_by_table.get(real.lower())
            if cols is not None and col.name.lower() not in cols:
                warnings.append(AnalysisWarning(
                    "warn", "UNKNOWN_COLUMN",
                    f'Spalte „{col.name}“ existiert nicht in Tabelle „{real}“.'))

    # --- AP-39: clause & structure extraction (display + graph) ---
    amap = _alias_map(node)
    columns: tuple[str, ...] = ()
    joins: list[dict] = []
    edges: list[tuple[str, str]] = []
    filters: tuple[str, ...] = ()
    group_by: tuple[str, ...] = ()
    having: tuple[str, ...] = ()
    order_by: tuple[str, ...] = ()
    distinct = False
    limit_txt: "str | None" = None

    if isinstance(node, exp.Select):
        columns = tuple(e.sql() for e in node.expressions)
        distinct = node.args.get("distinct") is not None
        for j in node.find_all(exp.Join):
            tbl = j.this
            on = j.args.get("on")
            joins.append({
                "kind": _join_kind(j),
                "table": tbl.name if isinstance(tbl, exp.Table) else tbl.sql(),
                "on": on.sql() if on is not None else "",
            })
            # Graph edges: connect every distinct pair of tables named in the ON.
            involved = _tables_in(on, amap)
            for a in range(len(involved)):
                for b in range(a + 1, len(involved)):
                    pair = (involved[a], involved[b])
                    if pair not in edges and (pair[1], pair[0]) not in edges:
                        edges.append(pair)
        where = node.args.get("where")
        filters = tuple(p.sql() for p in _split_and(where.this if where else None))
        grp = node.args.get("group")
        if grp is not None:
            group_by = tuple(e.sql() for e in grp.expressions)
        hav = node.args.get("having")
        if hav is not None:
            having = tuple(p.sql() for p in _split_and(hav.this))
        order = node.args.get("order")
        if order is not None:
            order_by = tuple(o.sql() for o in order.expressions)
        lim = node.args.get("limit")
        if lim is not None:
            limit_txt = lim.expression.sql() if lim.expression is not None else lim.sql()

    structure, score, grade = _structure_and_complexity(node)
    warnings.extend(_static_lints(node))
    suggestions = (_optimization_suggestions(node)
                   if isinstance(node, exp.Select) else [])

    return AnalysisResult(
        statement_type=stmt_type,
        tables_read=tuple(sorted(read)),
        tables_written=tuple(sorted(written)),
        warnings=tuple(warnings),
        parse_error=None,
        columns=columns,
        joins=tuple(joins),
        edges=tuple(edges),
        filters=filters,
        group_by=group_by,
        having=having,
        order_by=order_by,
        distinct=distinct,
        limit=limit_txt,
        structure=structure,
        complexity_score=score,
        complexity_grade=grade,
        suggestions=tuple(suggestions),
    )
