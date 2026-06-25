"""HTTP API: reflect a schema and compute join-path SQL. Read-only."""
import logging
import sys
from importlib.metadata import PackageNotFoundError, version as pkg_version

from flask import Blueprint, jsonify, render_template, request

import config

from core.loaders.sqlalchemy_loader import SqlAlchemyLoader
from core.graph import build_graph
from core.pathfinder import find_paths, NoPathError
from core.sqlgen import generate_sql, Selection, Filter
from core.settings import Settings
from core.ddl import table_ddl
from core.datapreview import fetch_rows

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


@bp.post("/api/schema")
def api_schema():
    """Reflect a database schema and return tables with their columns."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    try:
        schema = SqlAlchemyLoader(url).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(
        tables=[{
            "name": t.name,
            "columns": [
                {"name": c.name, "type": c.type, "pk": c.name in t.primary_key}
                for c in t.columns
            ],
            "foreign_keys": [
                {"column": fk.column, "ref_table": fk.ref_table,
                 "ref_column": fk.ref_column}
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


@bp.post("/api/data")
def api_data():
    """Return the first rows of a table or view (read-only preview)."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    obj = data.get("object", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    try:
        schema = SqlAlchemyLoader(url).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400
    valid = {t.name for t in schema.tables} | {v.name for v in schema.views}
    try:
        result = fetch_rows(url, obj, valid)
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
    try:
        schema = SqlAlchemyLoader(url).load()
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


@bp.post("/api/joinpath")
def api_joinpath():
    """Find join paths between two columns and return the generated SQL."""
    data = request.get_json(silent=True) or {}
    url = data.get("connection_url", "")
    if not url.strip():
        return jsonify(error=_NO_URL_MSG), 400
    try:
        schema = SqlAlchemyLoader(url).load()
    except ConnectionError as exc:
        return jsonify(error=str(exc)), 400

    include_implied = bool(data.get("include_implied", False))
    try:
        graph = build_graph(schema, include_implied)
    except Exception as exc:
        _log.exception("graph build failed")
        return jsonify(error="internal error building schema graph"), 500
    try:
        start = data["start"]
        target = data["target"]
        filters = tuple(
            Filter(f["table"], f["column"], f["op"], f["value"])
            for f in data.get("filters", [])
        )
        # Validate that every referenced column exists in the reflected schema.
        for tbl, col in ([(start["table"], start["column"]),
                          (target["table"], target["column"])] +
                         [(f.table, f.column) for f in filters]):
            if not schema.has_column(tbl, col):
                return jsonify(error=f"unknown column: {tbl}.{col}"), 400
        selects = (Selection(start["table"], start["column"]),
                   Selection(target["table"], target["column"]))
        filter_tables = tuple(f.table for f in filters)
        paths = find_paths(graph, start["table"], target["table"], filter_tables)
    except KeyError as exc:
        return jsonify(error=f"missing field: {exc}"), 400
    except NoPathError as exc:
        return jsonify(error=str(exc)), 400

    out = []
    try:
        for p in paths:
            gen = generate_sql(p, selects, filters)
            out.append({
                "tables": list(p.tables),
                "edges": [[s.left_table, s.right_table] for s in p.steps],
                "sql": gen.sql,
                "params": gen.params,
            })
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(paths=out)
