"""HTTP API: reflect a schema and compute join-path SQL. Read-only."""
import logging
import sys
from importlib.metadata import PackageNotFoundError, version as pkg_version

from flask import Blueprint, jsonify, render_template, request

import config

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader, list_schemas
from core.graph import build_graph
from core.pathfinder import find_paths, NoPathError
from core.sqlgen import generate_sql, Selection, Filter, Having, dialect_for, SQLITE
from core.settings import Settings
from core.ddl import table_ddl
from core.datapreview import fetch_rows, execute_select
from core.connection import build_url
from core.sqlanalyze import analyze as analyze_sql

# Connection fields that may be persisted (never the password).
_CONN_FIELDS = ("db_type", "host", "port", "database", "user", "filepath",
                "encrypt", "trust_server_certificate", "service_name")

_log = logging.getLogger("luDBxP")

# User-facing message for a missing/blank connection URL.
_NO_URL_MSG = "Bitte eine Connection-URL angeben (z. B. sqlite:///pfad/zur.db)."

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Serve the main single-page application shell.

    Prefills the connection URL from the saved default_connection setting so
    the first "Schema laden" click works out of the box.
    """
    default_connection = Settings.load().get("default_connection")
    return render_template("index.html", default_connection=default_connection)


def _pkg_version(name: str) -> str:
    try:
        return pkg_version(name)
    except PackageNotFoundError:
        return "?"


@bp.get("/api/info")
def api_info():
    """Return application metadata: name, version, author, and tech stack."""
    return jsonify(
        name=config.APP_NAME,
        version=config.APP_VERSION,
        author=config.APP_AUTHOR,
        stack=[
            {"name": "Python", "version": ".".join(map(str, sys.version_info[:3]))},
            {"name": "Flask", "version": _pkg_version("flask")},
            {"name": "SQLAlchemy", "version": _pkg_version("sqlalchemy")},
            {"name": "NetworkX", "version": _pkg_version("networkx")},
            {"name": "Cytoscape.js", "version": config.CYTOSCAPE_VERSION},
        ],
    )


@bp.post("/api/connect")
def api_connect():
    """Build a connection URL from structured params and test the connection."""
    data = request.get_json(silent=True) or {}
    try:
        url = build_url(data)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    try:
        SqlAlchemyLoader(url).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(connection_url=url)


@bp.get("/api/connections")
def api_connections_list():
    """List saved connections (without passwords)."""
    return jsonify(connections=Settings.load().get("connections") or [])


@bp.post("/api/connections")
def api_connections_save():
    """Save a named connection (password is never persisted)."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="Verbindungsname fehlt."), 400
    entry = {"name": name}
    entry.update({k: data.get(k) for k in _CONN_FIELDS})
    s = Settings.load()
    conns = [c for c in (s.get("connections") or []) if c.get("name") != name]
    conns.append(entry)
    s.set("connections", conns)
    s.save()
    return jsonify(connections=conns)


@bp.delete("/api/connections")
def api_connections_delete():
    """Delete a saved connection by name."""
    data = request.get_json(silent=True) or {}
    name = data.get("name") or ""
    s = Settings.load()
    conns = [c for c in (s.get("connections") or []) if c.get("name") != name]
    s.set("connections", conns)
    s.save()
    return jsonify(connections=conns)


@bp.post("/api/schema")
def api_schema():
    """Reflect a database schema and return tables with their columns."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(
        tables=[{
            "name": t.name,
            "comment": t.comment,
            "columns": [
                {"name": c.name, "type": c.type, "pk": c.name in t.primary_key,
                 "comment": c.comment}
                for c in t.columns
            ],
            "foreign_keys": [
                {"columns": list(fk.columns), "ref_table": fk.ref_table,
                 "ref_columns": list(fk.ref_columns)}
                for fk in t.foreign_keys
            ],
            "ddl": table_ddl(t),
        } for t in schema.tables],
        views=[{
            "name": v.name,
            "columns": [{"name": c.name, "type": c.type} for c in v.columns],
            "definition": v.definition,
        } for v in schema.views],
    )


@bp.post("/api/schemas")
def api_schemas():
    """List the database's user-facing schema names for the schema picker."""
    data = request.get_json(silent=True) or {}
    url = (data.get("connection_url") or "").strip()
    if not url:
        return jsonify(error=_NO_URL_MSG), 400
    try:
        schemas = list_schemas(url)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(schemas=list(schemas))


@bp.post("/api/data")
def api_data():
    """Return the first rows of a table or view (read-only preview)."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    obj = data.get("object", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    valid = {t.name for t in schema.tables} | {v.name for v in schema.views}
    try:
        result = fetch_rows(url, obj, valid, schema=schema_name)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(**result)


@bp.post("/api/graph")
def api_graph():
    """Return the FK graph as nodes and edges for visualization."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    include_implied = bool(data.get("include_implied", False))
    graph = build_graph(schema, include_implied)
    nodes = [{"id": n} for n in graph.nodes]
    edges = [
        {"source": a, "target": b, "implied": graph[a][b].get("implied", False)}
        for a, b in graph.edges
    ]
    return jsonify(nodes=nodes, edges=edges)


# ===== Join-path helpers (shared by /api/joinpath and /api/joinpath/run) =====

_JP_NULL_OPS = frozenset({"IS NULL", "IS NOT NULL"})


def _parse_joinpath_params(data: dict, schema):
    """Parse and validate all join-path parameters from request JSON.

    Returns a 9-tuple:
    ``(start, target, filters, extra_selections, distinct, limit,
       order_by_validated, having, required_tables)``

    Raises:
        KeyError: If a required field is absent.
        ValueError: If a parameter value is invalid (unknown column, bad
            ORDER BY direction, malformed BETWEEN value list, …).
    """
    start = data["start"]
    target = data["target"]

    # --- Filters ---
    raw_filters = data.get("filters", [])
    filters_list: list[Filter] = []
    for f in raw_filters:
        op = f["op"]
        if op in _JP_NULL_OPS:
            value = None
        elif op == "IN":
            raw_val = f.get("value") or []
            if isinstance(raw_val, list):
                value = [v for v in raw_val if v != "" and v is not None]
            else:
                value = [v.strip() for v in str(raw_val).split(",") if v.strip()]
            if not value:
                continue  # skip empty IN (no rows could match)
        elif op == "BETWEEN":
            raw_val = f.get("value") or []
            if len(raw_val) != 2:
                raise ValueError("BETWEEN requires exactly 2 values")
            value = tuple(raw_val)
        else:
            value = f["value"]
        filters_list.append(Filter(f["table"], f["column"], op, value))
    filters = tuple(filters_list)

    # --- Extra SELECT columns ---
    extra_selections = tuple(
        Selection(es["table"], es["column"], es.get("agg", ""))
        for es in data.get("extra_selects", [])
    )

    # --- AP-3: DISTINCT, LIMIT ---
    distinct = bool(data.get("distinct", False))
    limit_raw = data.get("limit")
    limit = None
    if limit_raw is not None:
        try:
            n = int(limit_raw)
            if n > 0:
                limit = n
        except (TypeError, ValueError):
            pass  # invalid/non-positive limit → no LIMIT clause

    # --- AP-3: ORDER BY — validate columns, keep direction allowlist ---
    raw_order_by = data.get("order_by", [])
    order_by_validated: list[tuple] = []
    for ob in raw_order_by:
        tbl = ob.get("table", "")
        col = ob.get("column", "")
        direction = (ob.get("dir") or "ASC").upper()
        agg = ob.get("agg", "")
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"invalid ORDER BY direction: {direction!r}")
        if not schema.has_column(tbl, col):
            raise ValueError(f"unknown column: {tbl}.{col}")
        order_by_validated.append((tbl, col, direction, agg))

    # --- HAVING: filter groups by an aggregate (scalar comparison, parametrised) ---
    raw_having = data.get("having", [])
    having_validated: list[Having] = []
    for h in raw_having:
        tbl = h.get("table", "")
        col = h.get("column", "")
        if not schema.has_column(tbl, col):
            raise ValueError(f"unknown column: {tbl}.{col}")
        having_validated.append(
            Having(tbl, col, h.get("agg", ""), h.get("op", ""), h.get("value")))
    having = tuple(having_validated)

    # --- Validate that every referenced column exists in the reflected schema ---
    for tbl, col in ([(start["table"], start["column"]),
                      (target["table"], target["column"])] +
                     [(f.table, f.column) for f in filters] +
                     [(s.table, s.column) for s in extra_selections]):
        if not schema.has_column(tbl, col):
            raise ValueError(f"unknown column: {tbl}.{col}")

    # AP-30: every table whose column is referenced (filter, extra select,
    # ORDER BY or HAVING) must be woven into the join tree. Order-preserving
    # dedup keeps path-finding deterministic (no set iteration).
    required_tables = tuple(dict.fromkeys(
        [f.table for f in filters]
        + [s.table for s in extra_selections]
        + [e[0] for e in order_by_validated]
        + [h.table for h in having_validated]
    ))
    return (start, target, filters, extra_selections,
            distinct, limit, order_by_validated, having, required_tables)


def _dialect_from_url(url: str):
    """Map a SQLAlchemy connection URL to its SQL Dialect (SQLite fallback)."""
    scheme = url.split("://", 1)[0].split("+", 1)[0]
    return dialect_for(scheme)


def _make_path_gen(p, start: dict, target: dict,
                   extra_selections: tuple,
                   filters: tuple,
                   distinct: bool,
                   limit,
                   order_by_validated: list,
                   dialect=SQLITE,
                   join_types: tuple = (),
                   schema: str = "",
                   having: tuple = ()):
    """Build a GeneratedSQL for a single join path.

    All extra selects and order_by entries are included; AP-30 guarantees
    their tables are woven into *p*.
    """
    seen: set[tuple[str, str, str]] = set()
    selects_for_path: list[Selection] = []
    for sel in (Selection(start["table"], start["column"], start.get("agg", "")),
                Selection(target["table"], target["column"], target.get("agg", "")),
                *extra_selections):
        key = (sel.table, sel.column, sel.agg)
        if key not in seen:
            seen.add(key)
            selects_for_path.append(sel)

    # AP-30 invariant: find_paths wove every referenced table into p, so each
    # extra-select column resolves to a joined table. Guard against a future
    # caller that forgets to pass required_tables (would emit invalid SQL).
    assert all(sel.table in set(p.tables) for sel in extra_selections), \
        "extra-select table missing from join path (required_tables not woven?)"

    # AP-30: every referenced table is now woven into the path, so order_by is
    # passed through unfiltered (no silent drop).
    order_by_for_path = tuple(order_by_validated)

    return generate_sql(p, tuple(selects_for_path), filters,
                        distinct=distinct,
                        order_by=order_by_for_path,
                        having=having,
                        limit=limit,
                        join_types=tuple(join_types),
                        dialect=dialect,
                        schema=schema)


def _path_warnings(p) -> list[str]:
    """Non-blocking warnings for a join path: one per descending (1-N) step,
    which can multiply result rows (quasi-cartesian fan-out)."""
    return [
        f'Ast „{s.right_table}“ ist 1-N (absteigend) — kann Zeilen vervielfachen.'
        for s in p.steps if s.to_many
    ]


@bp.post("/api/joinpath")
def api_joinpath():
    """Find join paths between two columns and return the generated SQL."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400

    include_implied = bool(data.get("include_implied", False))
    try:
        graph = build_graph(schema, include_implied)
    except Exception as exc:
        _log.exception("graph build failed")
        return jsonify(error="internal error building schema graph"), 500

    try:
        (start, target, filters, extra_selections,
         distinct, limit, order_by_validated, having,
         required_tables) = _parse_joinpath_params(data, schema)
        paths = find_paths(graph, start["table"], target["table"], required_tables)
    except KeyError as exc:
        return jsonify(error=f"missing field: {exc}"), 400
    except NoPathError as exc:
        return jsonify(error=str(exc)), 400
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    # Display dialect: the client's chosen SQL dialect (dropdown); falls back to
    # the connected DB's dialect when unspecified.
    dialect = (dialect_for(data["dialect"]) if data.get("dialect")
               else _dialect_from_url(url))

    # AP-41: optional per-step join types (INNER default), applied positionally.
    join_types = tuple(data.get("join_types") or ())

    out = []
    try:
        for p in paths:
            gen = _make_path_gen(p, start, target, extra_selections, filters,
                                 distinct, limit, order_by_validated, dialect,
                                 join_types=join_types, schema=schema_name,
                                 having=having)
            out.append({
                "tables": list(p.tables),
                "edges": [[s.left_table, s.right_table] for s in p.steps],
                # Per-step direction so the UI can label every join N-1 / 1-N,
                # not only flag the descending (to_many) ones via warnings.
                "steps": [
                    {"left": s.left_table, "right": s.right_table,
                     "to_many": s.to_many}
                    for s in p.steps
                ],
                "sql": gen.sql,
                # Runnable variant with filter values inlined (for copy/display);
                # `sql` + `params` remain the parameterised execution path.
                "sql_inline": gen.sql_inline,
                "params": gen.params,
                "warnings": _path_warnings(p),
            })
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(paths=out)


@bp.post("/api/joinpath/run")
def api_joinpath_run():
    """Execute the SQL for one join path and return tabular results.

    Accepts the same parameters as /api/joinpath plus an optional
    ``path_index`` (int, default 0) to select which path to execute and an
    optional ``max_rows`` (200/400/None=all). The requested row count is
    clamped to ``config.MAX_RESULT_ROWS``; ``None`` means "all up to the
    ceiling". Returns ``{columns, rows, sql, row_cap}``.

    Security: SQL is built server-side from join parameters via
    ``generate_sql`` — no client-supplied SQL string is ever executed.
    """
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400

    include_implied = bool(data.get("include_implied", False))
    try:
        graph = build_graph(schema, include_implied)
    except Exception as exc:
        _log.exception("graph build failed")
        return jsonify(error="internal error building schema graph"), 500

    try:
        (start, target, filters, extra_selections,
         distinct, limit, order_by_validated, having,
         required_tables) = _parse_joinpath_params(data, schema)
        paths = find_paths(graph, start["table"], target["table"], required_tables)
    except KeyError as exc:
        return jsonify(error=f"missing field: {exc}"), 400
    except NoPathError as exc:
        return jsonify(error=str(exc)), 400
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    # Select the requested path; clamp to valid range
    try:
        path_index = int(data.get("path_index") or 0)
    except (TypeError, ValueError):
        path_index = 0
    if path_index < 0 or path_index >= len(paths):
        path_index = 0

    # Execution must match the real backend → use the connection's own dialect
    # (not any client display choice), so the quoted SQL actually runs.
    run_dialect = _dialect_from_url(url)
    join_types = tuple(data.get("join_types") or ())
    try:
        gen = _make_path_gen(paths[path_index], start, target, extra_selections,
                             filters, distinct, limit, order_by_validated,
                             run_dialect, join_types=join_types, schema=schema_name,
                             having=having)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    # Result row cap: client may request 200/400 or None ("Alle"). Always
    # clamp to the hard ceiling so a huge join can never flood the browser.
    hard_cap = config.MAX_RESULT_ROWS
    req_rows = data.get("max_rows")
    if req_rows is None:
        max_rows = hard_cap
    else:
        try:
            max_rows = max(1, min(int(req_rows), hard_cap))
        except (TypeError, ValueError):
            max_rows = config.DEFAULT_RESULT_ROWS

    try:
        result = execute_select(url, gen.sql, gen.params, max_rows=max_rows)
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400

    # AP-45: per-output-column (table, column) map, in the exact order the SQL
    # generator emits selections (start, target, then extra selects, deduped).
    # Lets the result table trace each <th> back to its source column even when
    # two joined tables share a column name.
    seen: set = set()
    columns_meta = []
    for sel in (start, target, *({"table": s.table, "column": s.column}
                                 for s in extra_selections)):
        key = (sel["table"], sel["column"])
        if key not in seen:
            seen.add(key)
            columns_meta.append({"table": sel["table"], "column": sel["column"]})

    return jsonify(columns=result["columns"], rows=result["rows"],
                   sql=gen.sql, row_cap=max_rows, columns_meta=columns_meta)


@bp.post("/api/distinct")
def api_distinct():
    """AP-45: return the distinct values of one column for the filter-value
    dropdown. Read-only ``SELECT DISTINCT col FROM table WHERE col IS NOT NULL
    ORDER BY col``, capped at ``config.DISTINCT_LIMIT``. The (table, column) is
    validated against the reflected schema before being quoted in — not an
    injection vector. Best-effort like ``/api/orphan_check``: any problem
    (no connection, unknown column, unreachable DB) returns ``{"values": []}``
    with status 200 so the form is never blocked."""
    data = request.get_json(silent=True) or {}
    url = (data.get("connection_url") or "").strip()
    table = data.get("table") or ""
    column = data.get("column") or ""
    if not url or not table or not column:
        return jsonify(values=[])
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
        if not schema.has_column(table, column):
            return jsonify(values=[])
        dialect = _dialect_from_url(url)
        col = dialect.qualify(table, column, schema_name)
        sql = (f"SELECT DISTINCT {col} FROM {dialect.table_ref(table, schema_name)}\n"
               f"WHERE {col} IS NOT NULL\nORDER BY {col}")
        result = execute_select(url, sql, {}, max_rows=config.DISTINCT_LIMIT)
    except (ConnectionError, ValueError):
        return jsonify(values=[])
    values = [r[0] for r in result["rows"]]
    return jsonify(values=values)


@bp.post("/api/orphan_check")
def api_orphan_check():
    """Per join step of the chosen path: which join types would *actually* change
    the result row count (vs INNER at that step, with the other steps kept at the
    client's current types)? This counts the real query — so it accounts for path
    context (unreachable orphans) and downstream joins (orphans filtered out),
    avoiding the false positives an isolated per-table probe would give.

    Returns ``{"steps": [{"left": bool, "right": bool, "full": bool}, …]}``; an
    empty list in text-mode or on any error (best-effort hint, never blocks)."""
    data = request.get_json(silent=True) or {}
    url = (data.get("connection_url") or "").strip()
    if not url:
        return jsonify(steps=[])
    schema_name = (data.get("schema") or "").strip()
    try:
        schema = SqlAlchemyLoader(url).load(schema_name or None)
        graph = build_graph(schema, bool(data.get("include_implied", False)))
        (start, target, filters, extra_selections, distinct, limit,
         order_by_validated, having, required_tables) = _parse_joinpath_params(data, schema)
        paths = find_paths(graph, start["table"], target["table"], required_tables)
    except (ConnectionError, KeyError, NoPathError, ValueError):
        return jsonify(steps=[])
    try:
        path_index = int(data.get("path_index") or 0)
    except (TypeError, ValueError):
        path_index = 0
    if not (0 <= path_index < len(paths)):
        return jsonify(steps=[])

    p = paths[path_index]
    n = len(p.steps)
    dialect = _dialect_from_url(url)
    cur = list(data.get("join_types") or [])
    current = [(cur[i] if i < len(cur) else "INNER") or "INNER" for i in range(n)]

    def row_count(types) -> "int | None":
        try:
            gen = _make_path_gen(p, start, target, extra_selections, filters,
                                 distinct, None, [], dialect, join_types=tuple(types),
                                 schema=schema_name, having=having)
            wrapped = f"SELECT COUNT(*) AS c FROM (\n{gen.sql}\n) sub"
            res = execute_select(url, wrapped, gen.params, max_rows=1)
            return res["rows"][0][0] if res["rows"] else None
        except (ConnectionError, ValueError):
            return None

    out = []
    for k in range(n):
        base = list(current); base[k] = "INNER"
        c_inner = row_count(base)
        flags = {"left": False, "right": False, "full": False}
        if c_inner is not None:
            for key, kw in (("left", "LEFT"), ("right", "RIGHT"), ("full", "FULL")):
                t = list(current); t[k] = kw
                c = row_count(t)
                flags[key] = (c is not None and c != c_inner)
        out.append(flags)
    return jsonify(steps=out)


@bp.post("/api/analyze")
def api_analyze():
    """Analyze a pasted SQL statement read-only — never executes it.

    With a connection_url the reflected schema and the connection dialect feed
    table/column cross-checks; without one, the analysis is text-only.
    """
    data = request.get_json(silent=True) or {}
    sql = data.get("sql", "")
    if not sql.strip():
        return jsonify(error="Bitte ein SQL-Statement eingeben."), 400

    schema = None
    dialect = None
    url = (data.get("connection_url") or "").strip()
    if url:
        try:
            schema = SqlAlchemyLoader(url).load()
        except ConnectionError as exc:
            return jsonify(error=str(exc)), 400
        dialect = _dialect_from_url(url).name

    result = analyze_sql(sql, schema=schema, dialect=dialect)
    return jsonify(
        statement_type=result.statement_type,
        tables_read=list(result.tables_read),
        tables_written=list(result.tables_written),
        warnings=[{"level": w.level, "code": w.code, "message": w.message}
                  for w in result.warnings],
        suggestions=[{"code": s.code, "message": s.message}
                     for s in result.suggestions],
        parse_error=result.parse_error,
        # AP-39 — structure & clause analysis + graph edges
        columns=list(result.columns),
        joins=list(result.joins),
        edges=[list(e) for e in result.edges],
        filters=list(result.filters),
        group_by=list(result.group_by),
        having=list(result.having),
        order_by=list(result.order_by),
        distinct=result.distinct,
        limit=result.limit,
        structure=result.structure,
        complexity={"score": result.complexity_score,
                    "grade": result.complexity_grade},
    )
